"""Validation harness for the enumeration pipeline.

Three layers of checks, all runnable offline in the project venv:

1. Small-SRG enumeration: run the full encode -> ALL-SAT -> isomorph-reject
   pipeline on tiny parameter sets whose non-isomorphic counts are known, and
   confirm the pipeline reproduces them exactly.

2. Real SRG(37,18,8,9) recognition: build the Paley graph P(37) (a genuine
   SRG(37,18,8,9)), fix it as a seed, and confirm the n=37 encoding is
   satisfied by it (exactly one edge-model).  Also confirm P(37) passes every
   P1-P12 invariant check.

3. Negative control: perturb one edge of P(37) and confirm the encoding
   rejects it (no models).

If a directory ProcessFiles/known37/ containing graph6 files (e.g. Spence's
6760 or Maksimovic's 6 new graphs) is present, they are additionally verified
as SRG(37,18,8,9) and their invariant fingerprints are reported.
"""

from __future__ import annotations

import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "ProgramFiles")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from srg_encoder import SRGSpec  # noqa: E402
import properties  # noqa: E402
import iso  # noqa: E402
import sat_backend  # noqa: E402
from srg_encoder import CNFBuilder, add_srg_constraints  # noqa: E402
from Utilities.paley import generate_paley_matrix  # noqa: E402

# Reuse the pipeline runner.
sys.path.insert(0, _HERE)
from enumerate import run_enumeration  # noqa: E402


# (v, k, lam, mu, expected_non_isomorphic, backends, timeout, tier)
# Expected counts from Brouwer's tables of strongly regular graphs.
COUNT_MATRIX = [
    (5, 2, 0, 1, 1, "both", None, "fast"),    # C5
    (9, 4, 1, 2, 1, "both", None, "fast"),    # Paley(9)
    (10, 3, 0, 1, 1, "both", None, "fast"),   # Petersen
    (13, 6, 2, 3, 1, "smsg", 60, "fast"),     # Paley(13)
    (15, 6, 1, 3, 1, "smsg", 60, "fast"),     # GQ(2,2)
    (16, 6, 2, 2, 2, "smsg", 120, "fast"),    # Shrikhande + L(K4,4)
    (16, 5, 0, 2, 1, "smsg", 120, "fast"),    # Clebsch
    (25, 12, 5, 6, 15, "smsg", 900, "full"),  # Paulus graphs
    (26, 10, 3, 4, 10, "smsg", 900, "full"),
    (29, 14, 6, 7, 41, "smsg", 3600, "full"),  # conference graph (analog of 37)
]


def _run_backend(spec, backend, timeout, tag, out_dir):
    res = run_enumeration(
        spec,
        backend=backend,
        timeout=timeout,
        out_dir=out_dir,
        tag=tag,
    )
    return res["valid_srgs"], res["raw_models"], res["seconds"]


def check_count_matrix(full=False, out_dir="output"):
    print("== Layer 1: known-count matrix (encode -> ALL-SAT -> dedup) ==")
    all_ok = True
    for v, k, lam, mu, expected, backends, timeout, tier in COUNT_MATRIX:
        if tier == "full" and not full:
            print(f"  SRG{(v,k,lam,mu)}: skipped (use --full; expected {expected})")
            continue
        spec = SRGSpec(v, k, lam, mu)
        tag = f"validate_{v}_{k}_{lam}_{mu}"
        results = {}
        if backends in ("both", "pysat"):
            results["pysat"] = _run_backend(
                spec, "pysat", None, tag + "_pysat", out_dir
            )
        if backends in ("both", "smsg") and sat_backend.has_smsg():
            results["smsg"] = _run_backend(
                spec, "smsg", timeout, tag + "_smsg", out_dir
            )
        if not results:
            print(f"  SRG{(v,k,lam,mu)}: no backend available; skipped")
            continue
        counts = {b: r[0] for b, r in results.items()}
        ok = all(c == expected for c in counts.values())
        # backend agreement when both ran
        if "pysat" in counts and "smsg" in counts:
            ok &= counts["pysat"] == counts["smsg"]
        all_ok &= ok
        detail = ", ".join(f"{b}={counts[b]}" for b in counts)
        print(f"  SRG{(v,k,lam,mu)}: {detail}; expected {expected} -> "
              f"{'OK' if ok else 'FAIL'}")
    return all_ok


def _count_edge_models(spec, seed_matrix, limit=2):
    builder = CNFBuilder(spec.V)
    add_srg_constraints(builder, spec, seed_matrix=seed_matrix)
    raw = sat_backend.enumerate_pysat(builder, spec.V, limit=limit)
    return raw


def check_paley37():
    print("== Layer 2: Paley(37) recognition ==")
    spec = SRGSpec(37, 18, 8, 9)
    P = generate_paley_matrix(37)

    rep = properties.full_report(P, 37, 18, 8, 9)
    print(f"  P(37) is SRG(37,18,8,9): {rep['is_srg']}")
    print(f"  invariants: omega={rep['omega']} alpha={rep['alpha']} "
          f"CAB={rep['clique_adjacency_bound']} "
          f"2-rank={rep['2_rank']} 3-rank={rep['3_rank']}")

    raw = _count_edge_models(spec, P, limit=2)
    ok = rep["is_srg"] and len(raw) == 1
    print(f"  encoding admits P(37) as the unique edge-model: "
          f"{len(raw)} model(s) -> {'OK' if ok else 'FAIL'}")
    return ok, rep


def check_negative():
    print("== Layer 3: negative control (perturbed P(37)) ==")
    spec = SRGSpec(37, 18, 8, 9)
    P = generate_paley_matrix(37)
    # flip a single edge -> no longer strongly regular
    i, j = 0, 1
    P[i][j] = P[j][i] = 1 - P[i][j]
    raw = _count_edge_models(spec, P, limit=1)
    ok = len(raw) == 0
    print(f"  perturbed P(37) rejected by encoding: {len(raw)} model(s) -> "
          f"{'OK' if ok else 'FAIL'}")
    return ok


def check_known_library(expected=6766):
    lib = os.path.join(_ROOT, "ProcessFiles", "known37")
    union = os.path.join(lib, "all_canonical.g6")
    if os.path.exists(union):
        print("== Layer 4: known-graph ground-truth DB ==")
        with open(union) as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
        # confirm canonical + distinct
        distinct = len(set(iso.canonical_forms(lines)))
        # verify a random sample are genuine SRG(37,18,8,9)
        import random
        sample = random.sample(lines, min(50, len(lines)))
        bad = sum(0 if properties.verify_srg(
            iso.graph6_to_matrix(g), 37, 18, 8, 9)["ok"] else 1 for g in sample)
        ok = (distinct == expected) and (bad == 0)
        print(f"  DB size: {len(lines)} lines, {distinct} distinct canonical")
        print(f"  sample verify ({len(sample)}): {bad} failures")
        print(f"  matches expected {expected}: {distinct == expected} -> "
              f"{'OK' if ok else 'FAIL'}")
        return ok
    files = sorted(glob.glob(os.path.join(lib, "*.g6")))
    if not files:
        print("== Layer 4: known-graph library == (none found; skipping)")
        print(f"   (run Automators/build_known_db.py to populate {lib})")
        return True
    print(f"== Layer 4: verifying {len(files)} known graph6 file(s) ==")
    all_ok = True
    seen = set()
    for path in files:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                M = iso.graph6_to_matrix(line)
                all_ok &= properties.verify_srg(M, 37, 18, 8, 9)["ok"]
                seen.add(iso.canonical_form(line))
    print(f"  all verified as SRG(37,18,8,9): {all_ok}")
    print(f"  distinct canonical graphs: {len(seen)}")
    return all_ok


def main():
    import argparse
    ap = argparse.ArgumentParser(description="SRG enumeration validation harness")
    ap.add_argument("--full", action="store_true",
                    help="also run the slow count-matrix rows (25,26,29)")
    ap.add_argument("--out", default="output",
                    help="output root directory (default: output)")
    args = ap.parse_args()

    results = {
        "count_matrix": check_count_matrix(full=args.full, out_dir=args.out),
        "paley37": check_paley37()[0],
        "negative": check_negative(),
        "known_library": check_known_library(),
    }
    print("\n== summary ==")
    print(json.dumps(results, indent=2))
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
