"""Main enumeration pipeline: encode -> solve (ALL-SAT) -> isomorph-reject ->
validate -> save.

Backend selection:
  * ``smsg`` (SAT Modulo Symmetries) when the binary is available -> isomorph
    free enumeration with dynamic symmetry breaking;
  * otherwise PySAT + CaDiCaL projected ALL-SAT, with nauty for isomorph
    rejection afterwards.

Both consume the SMS-compatible encoding from :mod:`srg_encoder`.

Examples
--------
Enumerate a small SRG end-to-end (validates the whole pipeline)::

    python Automators/enumerate.py --v 5 --k 2 --lam 0 --mu 1 --tag c5

Enumerate SRG(37,18,8,9) extensions of a fixed K5 anchor with the clique
bound baked in (heavy; intended for smsg / staged runs)::

    python Automators/enumerate.py --fix-clique 5 --forbid-clique 5 \
        --forbid-independent 5 --tag k5anchor
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "ProgramFiles")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from srg_encoder import CNFBuilder, add_srg_constraints, SRGSpec, make_spec  # noqa: E402
import sat_backend  # noqa: E402
import iso  # noqa: E402
import properties  # noqa: E402
from output_layout import (  # noqa: E402
    is_authoritative_full_enum,
    publish_run_artifacts,
    resolve_output_root,
    run_dir,
    srg_id,
    utc_now_iso,
)
from Utilities.graphReader import get_graph  # noqa: E402


def _seed_from_file(path):
    matrix, *_ = get_graph(path)
    return matrix


def run_enumeration(
    spec: SRGSpec,
    *,
    seed_matrix=None,
    fix_clique: int = 0,
    forbid_clique=None,
    forbid_independent=None,
    backend: str = "auto",
    limit=None,
    timeout=None,
    out_dir: str = "output",
    tag: str = "run",
    frequency: int = 20,
    cutoff: int = 20000,
    keep_cnf: bool = False,
    live_progress: bool = False,
    progress_interval: float = 10.0,
):
    properties.validate_srg_parameters(spec.V, spec.degree, spec.lam, spec.mu)

    output_root = resolve_output_root(_ROOT, out_dir)
    out_dir = run_dir(spec, output_root, tag)
    os.makedirs(out_dir, exist_ok=True)
    started_at = utc_now_iso()
    t0 = time.time()

    builder = CNFBuilder(spec.V)
    meta = add_srg_constraints(
        builder, spec,
        seed_matrix=seed_matrix,
        fix_clique=fix_clique,
        forbid_clique=forbid_clique,
        forbid_independent=forbid_independent,
    )
    encode_stats = {
        "vertices": spec.V,
        "edge_vars": meta["num_edge_vars"],
        "total_vars": builder.nvars,
        "clauses": len(builder.clauses),
        "initial_partition": meta["initial_partition"],
    }

    use_smsg = backend == "smsg" or (backend == "auto" and sat_backend.has_smsg())
    if use_smsg:
        dimacs = os.path.join(out_dir, "formula.cnf")
        builder.to_dimacs(dimacs)
        try:
            raw_result = sat_backend.run_smsg(
                dimacs, spec.V,
                initial_partition=meta["initial_partition"],
                frequency=frequency, cutoff=cutoff, limit=limit, timeout=timeout,
                progress=live_progress,
                progress_interval=progress_interval,
            )
            raw = raw_result["matrices"]
        finally:
            if not keep_cnf and os.path.exists(dimacs):
                os.remove(dimacs)
                dimacs = None
        engine = "smsg"
        backend_reported_models = raw_result["n_graphs"]
        backend_completed = raw_result["completed"]
        backend_timed_out = raw_result["timed_out"]
    else:
        raw = sat_backend.enumerate_pysat(builder, spec.V, limit=limit)
        engine = "pysat+cadical"
        dimacs = None
        backend_reported_models = len(raw)
        backend_completed = limit is None
        backend_timed_out = False

    reps = iso.dedup_matrices(raw) if raw else []

    valid = []
    for m in reps:
        rep = properties.verify_srg(m, spec.V, spec.degree, spec.lam, spec.mu)
        if rep["ok"]:
            valid.append(m)

    valid_g6 = [iso.matrix_to_graph6(m) for m in valid]

    ended_at = utc_now_iso()
    elapsed = round(time.time() - t0, 3)
    search_complete = bool(backend_completed and limit is None)
    limiting_reason = []
    if limit is not None:
        limiting_reason.append("limit")
    if use_smsg and timeout is not None and backend_timed_out:
        limiting_reason.append("timeout")

    authoritative = is_authoritative_full_enum(
        search_complete=search_complete,
        fix_clique=fix_clique,
        forbid_clique=forbid_clique,
        forbid_independent=forbid_independent,
        limit=limit,
    )

    result = {
        "schema_version": 2,
        "srg_id": srg_id(spec),
        "tag": tag,
        "engine": engine,
        "params": list(spec),
        "started_at": started_at,
        "finished_at": ended_at,
        "encode": encode_stats,
        "raw_models": len(raw),
        "backend_reported_models": backend_reported_models,
        "non_isomorphic": len(reps),
        "valid_srgs": len(valid),
        "seconds": elapsed,
        "search_complete": search_complete,
        "limiting_reason": limiting_reason,
        "backend": {
            "requested": backend,
            "selected": engine,
            "completed": backend_completed,
            "timed_out": backend_timed_out,
        },
        "constraints": {
            "fix_clique": fix_clique,
            "forbid_clique": forbid_clique,
            "forbid_independent": forbid_independent,
            "limit": limit,
            "timeout": timeout,
        },
        "artifacts": {
            "formula_cnf": dimacs,
        },
    }
    published = publish_run_artifacts(
        spec,
        output_root,
        tag=tag,
        run_dir_path=out_dir,
        graph6_lines=valid_g6,
        summary=result,
        source="run",
        search_complete=search_complete,
        authoritative_full_enum=authoritative,
    )
    result["artifacts"].update(published)
    result["output_g6"] = published["run_g6"]
    result["output_jsonl"] = published["run_jsonl"]
    return result


def main():
    ap = argparse.ArgumentParser(description="SRG ALL-SAT enumeration pipeline")
    ap.add_argument("--v", type=int, default=37)
    ap.add_argument("--k", type=int, default=18)
    ap.add_argument("--lam", type=int, default=8)
    ap.add_argument("--mu", type=int, default=9)
    ap.add_argument("--seed", help="graph.txt seed adjacency matrix to fix")
    ap.add_argument("--fix-clique", type=int, default=0,
                    help="force vertices 0..t-1 to form a clique (anchor)")
    ap.add_argument("--forbid-clique", type=int, default=None,
                    help="forbid cliques larger than this (e.g. 5)")
    ap.add_argument("--forbid-independent", type=int, default=None,
                    help="forbid independent sets larger than this (e.g. 5)")
    ap.add_argument("--backend", choices=["auto", "smsg", "pysat"], default="auto")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--timeout", type=float, default=None,
                    help="wall-clock seconds before stopping smsg enumeration")
    ap.add_argument("--out", default="output",
                    help="output root directory (default: output)")
    ap.add_argument("--tag", default="run")
    ap.add_argument("--frequency", type=int, default=20)
    ap.add_argument("--cutoff", type=int, default=20000)
    ap.add_argument("--keep-cnf", action="store_true",
                    help="keep the generated DIMACS file (smsg backend)")
    ap.add_argument("--live-progress", action="store_true",
                    help="print elapsed timer + graph count while smsg runs")
    ap.add_argument("--progress-interval", type=float, default=10.0,
                    help="seconds between live timer updates")
    args = ap.parse_args()

    spec = make_spec(args.v, args.k, args.lam, args.mu)
    seed = _seed_from_file(args.seed) if args.seed else None
    res = run_enumeration(
        spec,
        seed_matrix=seed,
        fix_clique=args.fix_clique,
        forbid_clique=args.forbid_clique,
        forbid_independent=args.forbid_independent,
        backend=args.backend,
        limit=args.limit,
        timeout=args.timeout,
        out_dir=args.out,
        tag=args.tag,
        frequency=args.frequency,
        cutoff=args.cutoff,
        keep_cnf=args.keep_cnf,
        live_progress=args.live_progress,
        progress_interval=args.progress_interval,
    )
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
