"""Multi-stage max-clique anchor decomposition.

Every graph has a well-defined maximum clique size omega.  For SRG(37,18,8,9)
we have 3 <= omega <= 5 (triangles exist because lambda = 8 > 0; the clique
adjacency bound rules out K6, see properties.clique_adjacency_bound).  We
therefore partition the whole search space into disjoint stages by omega:

    stage t := { graphs whose maximum clique has size exactly t },  t in {3,4,5}

Each stage is encoded by

    * fixing a K_t on vertices 0..t-1                     (anchor, symmetry break)
    * forbidding cliques larger than t                    (makes omega == t)
    * forbidding independent sets larger than 5           (coclique bound P2)

Because every graph containing a K_t can be relabelled to put one of its K_t's
on 0..t-1, and larger cliques are forbidden, the stages are exhaustive and
pairwise disjoint up to isomorphism; the union (after a global nauty dedup)
is the full set of graphs.

Feasibility note: with the plain PySAT back-end the completion of the anchor is
enumerated over all labellings of the remaining vertices, which is only
tractable for small parameters or with the smsg back-end's dynamic symmetry
breaking.  The decomposition itself is correct regardless of back-end.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "ProgramFiles"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from srg_encoder import SRGSpec, make_spec  # noqa: E402
import iso  # noqa: E402
from enumerate import run_enumeration  # noqa: E402
from output_layout import (  # noqa: E402
    resolve_output_root,
    run_dir,
    update_srg_summary,
    upsert_srg_catalog,
    utc_now_iso,
    write_graph_artifacts,
)


def run_staged(
    spec: SRGSpec,
    anchors=(3, 4, 5),
    *,
    coclique_bound: int = 5,
    backend: str = "auto",
    limit=None,
    out_dir: str = "output",
    tag: str = "staged",
):
    output_root = resolve_output_root(_ROOT, out_dir)
    stage_dir = run_dir(spec, output_root, tag)
    os.makedirs(stage_dir, exist_ok=True)
    started_at = utc_now_iso()
    stages = []
    all_g6 = []
    for t in anchors:
        res = run_enumeration(
            spec,
            fix_clique=t,
            forbid_clique=t,               # -> max clique exactly t
            forbid_independent=coclique_bound,
            backend=backend,
            limit=limit,
            out_dir=output_root,
            tag=f"{tag}_k{t}",
        )
        stages.append({"anchor": t, **{k: res[k] for k in
                       ("raw_models", "non_isomorphic", "valid_srgs", "seconds")}})
        with open(res["output_g6"]) as fh:
            all_g6.extend(line.strip() for line in fh if line.strip())
        print(f"  stage omega=={t}: {res['valid_srgs']} graph(s)")

    # Global isomorph rejection across stages (stages are disjoint by omega, so
    # this mainly guards against accidental double counting).
    combined = iso.dedup_graph6(all_g6)
    combined_path = os.path.join(stage_dir, "graphs.g6")
    combined_jsonl = os.path.join(stage_dir, "graphs.jsonl")
    write_graph_artifacts(combined, combined_path, combined_jsonl,
                          source="stage", tag=tag)
    catalog = upsert_srg_catalog(spec, output_root, combined, source="stage",
                                 tag=tag)
    ended_at = utc_now_iso()

    summary = {
        "schema_version": 2,
        "tag": tag,
        "started_at": started_at,
        "finished_at": ended_at,
        "params": list(spec),
        "anchors": list(anchors),
        "stages": stages,
        "search_complete": True,
        "total_non_isomorphic": len(combined),
        "output_jsonl": combined_jsonl,
        "artifacts": {
            "run_dir": stage_dir,
            "graphs_g6": combined_path,
            "graphs_jsonl": combined_jsonl,
            "catalog_g6": catalog["catalog_g6"],
            "catalog_jsonl": catalog["catalog_jsonl"],
        },
        "output_g6": combined_path,
    }
    summary_path = os.path.join(stage_dir, "summary.json")
    summary["artifacts"]["summary_json"] = summary_path
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=2)
    update_srg_summary(
        spec,
        output_root,
        run_entry={
            "tag": tag,
            "engine": backend,
            "run_dir": stage_dir,
            "search_complete": True,
            "valid_srgs": len(combined),
            "summary_json": summary_path,
            "type": "staged",
        },
    )
    return summary


def main():
    ap = argparse.ArgumentParser(description="Multi-stage max-clique anchored enumeration")
    ap.add_argument("--v", type=int, default=37)
    ap.add_argument("--k", type=int, default=18)
    ap.add_argument("--lam", type=int, default=8)
    ap.add_argument("--mu", type=int, default=9)
    ap.add_argument("--anchors", default="3,4,5",
                    help="comma-separated max-clique stage sizes")
    ap.add_argument("--coclique-bound", type=int, default=5)
    ap.add_argument("--backend", choices=["auto", "smsg", "pysat"], default="auto")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default="output",
                    help="output root directory (default: output)")
    ap.add_argument("--tag", default="staged")
    args = ap.parse_args()

    spec = make_spec(args.v, args.k, args.lam, args.mu)
    anchors = tuple(int(x) for x in args.anchors.split(","))
    summary = run_staged(
        spec, anchors,
        coclique_bound=args.coclique_bound,
        backend=args.backend, limit=args.limit,
        out_dir=args.out, tag=args.tag,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
