"""Build the ground-truth database of known SRG(37,18,8,9) graphs.

Sources (downloaded into ProcessFiles/known37_raw/):
  * Spence's 6760 graphs           -> spence_37 (37x37 0/1 blocks, blank-separated)
  * Maksimovic's 6 graphs          -> maksimovic_srg37.txt (GAP adjacency records)
  * Paley(37)                      -> generated locally (a guaranteed member)

For every graph we:
  1. verify it is a genuine SRG(37,18,8,9);
  2. compute its nauty canonical graph6 form (batched via labelg);
  3. compute a cheap invariant fingerprint (2-rank, 3-rank over GF(p)).

Outputs (ProcessFiles/known37/):
  * all_canonical.g6   -- deduped canonical union (the diff target for mass enum)
  * <source>.g6        -- canonical forms per source
  * fingerprints.json  -- {canonical_g6: {"r2":.., "r3":.., "sources":[...]}}
  * summary.json       -- counts, overlaps, newly-found graphs

Run:  python Automators/build_known_db.py
"""

from __future__ import annotations

import ast
import glob
import json
import os
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "ProgramFiles")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import iso  # noqa: E402
import properties  # noqa: E402
import twographs as tg  # noqa: E402
from Utilities.paley import generate_paley_matrix  # noqa: E402

RAW = os.path.join(_ROOT, "ProcessFiles", "known37_raw")
OUT = os.path.join(_ROOT, "ProcessFiles", "known37")
V, K, LAM, MU = 37, 18, 8, 9


# --------------------------------------------------------------------------- #
# Source parsers.                                                             #
# --------------------------------------------------------------------------- #
def load_spence(path):
    """37x37 blocks of '0'/'1' rows separated by blank lines."""
    mats = []
    with open(path) as fh:
        block = []
        for line in fh:
            line = line.strip()
            if not line:
                if block:
                    mats.append([[int(c) for c in r] for r in block])
                    block = []
                continue
            block.append(line)
        if block:
            mats.append([[int(c) for c in r] for r in block])
    return mats


def load_maksimovic(path):
    """Parse GAP `gamaN:=rec(adjacencies := [[..1-indexed..],...], ...)` records."""
    text = open(path).read()
    mats = []
    for m in re.finditer(r"adjacencies\s*:=\s*", text):
        start = text.find("[", m.end())
        # balanced-bracket scan
        depth = 0
        i = start
        while i < len(text):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        adj_list = ast.literal_eval(text[start:i + 1])
        n = len(adj_list)
        mat = [[0] * n for _ in range(n)]
        for u, nbrs in enumerate(adj_list):
            for w in nbrs:
                mat[u][w - 1] = 1  # 1-indexed -> 0-indexed
        # symmetrise defensively
        for a in range(n):
            for b in range(a + 1, n):
                if mat[a][b] or mat[b][a]:
                    mat[a][b] = mat[b][a] = 1
        mats.append(mat)
    return mats


# --------------------------------------------------------------------------- #
# Build.                                                                       #
# --------------------------------------------------------------------------- #
def _verify_all(mats, label, verify_sample=None):
    """Verify (all or a sample of) matrices are SRG(37,18,8,9)."""
    idxs = range(len(mats))
    if verify_sample is not None and verify_sample < len(mats):
        step = max(1, len(mats) // verify_sample)
        idxs = range(0, len(mats), step)
    bad = 0
    for i in idxs:
        if not properties.verify_srg(mats[i], V, K, LAM, MU)["ok"]:
            bad += 1
    print(f"  [{label}] verified {len(list(idxs))}/{len(mats)}; "
          f"failures: {bad}")
    return bad == 0


def build(verify_sample=None):
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    sources = {}

    spence_path = os.path.join(RAW, "spence_37")
    if os.path.exists(spence_path):
        sources["spence"] = load_spence(spence_path)
        print(f"loaded spence: {len(sources['spence'])} graphs")

    mak_path = os.path.join(RAW, "maksimovic_srg37.txt")
    if os.path.exists(mak_path):
        sources["maksimovic"] = load_maksimovic(mak_path)
        print(f"loaded maksimovic: {len(sources['maksimovic'])} graphs")

    sources["paley"] = [generate_paley_matrix(37)]
    print("loaded paley: 1 graph")

    # Verify (Spence's 6760 fully-verified takes a few minutes; allow sampling).
    for label, mats in sources.items():
        vs = verify_sample if label == "spence" else None
        _verify_all(mats, label, verify_sample=vs)

    # Canonicalise per source (batched) and build the union.
    canon_by_source = {}
    all_canon = []
    for label, mats in sources.items():
        g6s = [iso.matrix_to_graph6(m) for m in mats]
        canon = iso.canonical_forms(g6s)
        canon_by_source[label] = canon
        all_canon.extend(canon)
        with open(os.path.join(OUT, f"{label}.g6"), "w") as fh:
            fh.write("\n".join(canon) + "\n")
        print(f"  [{label}] {len(canon)} graphs, {len(set(canon))} distinct")

    union = sorted(set(all_canon))
    with open(os.path.join(OUT, "all_canonical.g6"), "w") as fh:
        fh.write("\n".join(union) + "\n")
    print(f"union distinct canonical graphs: {len(union)}")

    # Which sources contain each canonical graph; find graphs beyond Spence.
    spence_set = set(canon_by_source.get("spence", []))
    new_beyond_spence = {}
    for label, canon in canon_by_source.items():
        if label == "spence":
            continue
        extra = sorted(set(canon) - spence_set)
        if extra:
            new_beyond_spence[label] = extra
            print(f"  [{label}] {len(extra)} graph(s) NOT in Spence's set")

    # Fingerprints (2-rank, 3-rank) for the union.
    fingerprints = {}
    for i, c in enumerate(union):
        M = iso.graph6_to_matrix(c)
        fingerprints[c] = {
            "r2": properties.rank_mod_p(M, 2),
            "r3": properties.rank_mod_p(M, 3),
            "sources": [s for s in canon_by_source if c in set(canon_by_source[s])],
        }
        if (i + 1) % 1000 == 0:
            print(f"  fingerprinted {i + 1}/{len(union)}")
    with open(os.path.join(OUT, "fingerprints.json"), "w") as fh:
        json.dump(fingerprints, fh)

    # Seidel-switching closure: complete the switching classes (regular
    # two-graphs on V+1 vertices).  The catalogued union need not be
    # switching-closed; its closure is the natural two-graph-route baseline.
    closure, n_classes, n_new = _switching_closure(union)
    with open(os.path.join(OUT, "switching_closure.g6"), "w") as fh:
        fh.write("\n".join(closure) + ("\n" if closure else ""))
    new_via_switch = sorted(set(closure) - set(union))
    with open(os.path.join(OUT, "switching_new.g6"), "w") as fh:
        fh.write("\n".join(new_via_switch) + ("\n" if new_via_switch else ""))
    print(f"switching closure: {len(closure)} graphs in {n_classes} "
          f"two-graph classes (+{n_new} beyond the catalogued union)")

    summary = {
        "params": [V, K, LAM, MU],
        "source_counts": {k: len(v) for k, v in sources.items()},
        "source_distinct": {k: len(set(v)) for k, v in canon_by_source.items()},
        "union_distinct": len(union),
        "new_beyond_spence": {k: len(v) for k, v in new_beyond_spence.items()},
        "switching_closure_size": len(closure),
        "two_graph_classes": n_classes,
        "new_via_switching": n_new,
        "rank_buckets": _bucket_counts(fingerprints),
        "build_seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(OUT, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print("\n== summary ==")
    print(json.dumps(summary, indent=2))
    return summary


def _switching_closure(seed_g6):
    """Close a set of SRG(37,18,8,9) graph6 strings under Seidel switching.

    Switching families are complete switching classes (idempotent), so a single
    sweep with a worklist reaches the closure.  Returns (closed_g6_sorted,
    n_classes, n_new_beyond_seed).
    """
    closed = set(seed_g6)
    n_classes = 0
    seen = set()
    frontier = list(seed_g6)
    while frontier:
        g6 = frontier.pop()
        if g6 in seen:
            continue
        fam = set(tg.switching_family_srg37(iso.graph6_to_matrix(g6)))
        n_classes += 1
        new = fam - closed
        closed |= fam
        seen |= fam
        frontier.extend(new)
    closed = sorted(set(iso.canonical_forms(sorted(closed))))
    n_new = len(set(closed) - set(seed_g6))
    return closed, n_classes, n_new


def _bucket_counts(fingerprints):
    buckets = {}
    for fp in fingerprints.values():
        key = f"r2={fp['r2']},r3={fp['r3']}"
        buckets[key] = buckets.get(key, 0) + 1
    return buckets


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-sample", type=int, default=None,
                    help="verify only ~N sampled Spence graphs (default: all)")
    args = ap.parse_args()
    build(verify_sample=args.verify_sample)
