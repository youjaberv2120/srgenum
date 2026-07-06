"""Cube-and-conquer mass-enumeration orchestrator (resumable, checkpointed).

Pipeline for one *campaign* (one parameter set + encoding + cube split):

  1. encode the SRG CNF (srg_encoder) once            -> <campaign>/formula.cnf
  2. generate cubes with smsg --simple-assignment-cutoff -> <campaign>/cubes.txt
  3. solve each cube independently (thread pool, per-cube timeout), streaming
     graphs, canonicalising per cube                  -> <campaign>/shards/*.g6
  4. checkpoint after every cube (atomic state.json), so the run is resumable
  5. incrementally merge shards -> nauty-deduped union -> <campaign>/canonical.g6
     and diff against the known ground-truth DB       -> <campaign>/new_candidates.g6

Because smsg's minimality check is *global* (a graph is emitted only if it is the
lexicographic minimum of its isomorphism class), the union of the per-cube
outputs over a complete cube partition is already isomorph-free; nauty dedup is
applied anyway as an independent safety net and to diff against known graphs.

Design choices for long unattended local runs (per user):
  * atomic checkpointing + resume (skip finished cubes)
  * per-cube timeout so one hard cube cannot stall the campaign
  * disk rotation: shards gzip'd after being merged (unless --keep-shards)
  * a cube that times out is recorded as PARTIAL and can be re-cubed/retried

Usage examples:
  # dress rehearsal (fully enumerate SRG(29,14,6,7) = 41):
  python Automators/mass_enumerate.py --v 29 --k 14 --lam 6 --mu 7 \
      --cube-cutoff 12 --workers 6 --cube-timeout 600 --tag rehearsal29

  # resume the same campaign after an interruption:
  python Automators/mass_enumerate.py --tag rehearsal29 --resume
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "ProgramFiles")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sat_backend as sb  # noqa: E402
import iso  # noqa: E402
from srg_encoder import CNFBuilder, add_srg_constraints, SRGSpec, make_spec  # noqa: E402
import properties  # noqa: E402
from output_layout import (  # noqa: E402
    campaign_dir as campaign_path_for_spec,
    discover_campaign_dirs,
    legacy_campaign_dir,
    resolve_output_root,
    srg_id,
    update_srg_summary,
    upsert_srg_catalog,
    utc_now_iso,
    write_graph_artifacts,
)


def _atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.replace(tmp, path)


class Campaign:
    def __init__(self, campaign_dir, output_root=None):
        self.dir = campaign_dir
        self.output_root = output_root
        self.shards = os.path.join(self.dir, "shards")
        self.cfg_path = os.path.join(self.dir, "config.json")
        self.state_path = os.path.join(self.dir, "state.json")
        self.cubes_path = os.path.join(self.dir, "cubes.txt")
        self.cnf_path = os.path.join(self.dir, "formula.cnf")
        self.canon_path = os.path.join(self.dir, "canonical.g6")
        self.canon_jsonl_path = os.path.join(self.dir, "canonical.jsonl")
        self.new_path = os.path.join(self.dir, "new_candidates.g6")
        self.log_path = os.path.join(self.dir, "log.txt")
        self._lock = threading.Lock()
        self.config = None
        self.state = None

    # ----------------------------------------------------------------- setup
    def log(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        with open(self.log_path, "a") as fh:
            fh.write(line + "\n")

    def load(self):
        with open(self.cfg_path) as fh:
            self.config = json.load(fh)
        with open(self.state_path) as fh:
            self.state = json.load(fh)
        if self.output_root is None:
            self.output_root = self.config.get("output_root")

    def save_state(self):
        with self._lock:
            _atomic_write(self.state_path, json.dumps(self.state, indent=1))

    def init(
        self,
        spec,
        cube_cutoff,
        encoder_opts,
        cube_timeout,
        known_db=None,
        campaign_tag=None,
    ):
        os.makedirs(self.shards, exist_ok=True)
        properties.validate_srg_parameters(
            spec.V, spec.degree, spec.lam, spec.mu
        )
        self.log(f"encoding CNF for SRG{spec}")
        builder = CNFBuilder(spec.V)
        meta = add_srg_constraints(builder, spec, **encoder_opts)
        builder.to_dimacs(self.cnf_path)
        self.log(f"CNF: {builder.nvars} vars, {len(builder.clauses)} clauses; "
                 f"partition={meta['initial_partition']}")

        self.log(f"generating cubes (simple-assignment-cutoff={cube_cutoff})")
        cubes = sb.generate_cubes(
            self.cnf_path, spec.V, cube_cutoff,
            initial_partition=meta["initial_partition"])
        with open(self.cubes_path, "w") as fh:
            fh.write("\n".join(cubes) + ("\n" if cubes else ""))
        self.log(f"{len(cubes)} cubes")

        self.config = {
            "schema_version": 2,
            "srg_id": srg_id(spec),
            "campaign_tag": campaign_tag,
            "params": [spec.V, spec.degree, spec.lam, spec.mu],
            "initial_partition": meta["initial_partition"],
            "cube_cutoff": cube_cutoff,
            "cube_timeout": cube_timeout,
            "encoder_opts": encoder_opts,
            "known_db": known_db,
            "n_cubes": len(cubes),
            "output_root": self.output_root,
            "campaign_dir": self.dir,
            "created_at": utc_now_iso(),
        }
        _atomic_write(self.cfg_path, json.dumps(self.config, indent=1))
        self.state = {
            "cubes": {str(i): {"status": "pending"}
                      for i in range(1, len(cubes) + 1)},
            "started": time.time(),
            "started_at": utc_now_iso(),
        }
        self.save_state()

    # --------------------------------------------------------------- solving
    def _solve_cube(self, i):
        t0 = time.time()
        v = self.config["params"][0]
        # Use ONLY the Python watchdog for the per-cube limit: smsg's own
        # --cube-timeout abandons a cube but still exits "normally", which would
        # look like a completed cube.  The watchdog instead kills the process so
        # the run is correctly reported as incomplete (status "timeout").
        r = sb.run_smsg(
            self.cnf_path, v,
            initial_partition=self.config["initial_partition"],
            cube_file=self.cubes_path, cube_line=i,
            timeout=self.config["cube_timeout"],
        )
        # canonicalise this cube's graphs and write a shard
        g6s = [iso.matrix_to_graph6(m) for m in r["matrices"]]
        canon = iso.canonical_forms(g6s) if g6s else []
        shard = os.path.join(self.shards, f"cube_{i:06d}.g6")
        with open(shard, "w") as fh:
            fh.write("\n".join(canon) + ("\n" if canon else ""))
        return {
            "status": "done" if r["completed"] else "timeout",
            "n_graphs": r["n_graphs"] if r["n_graphs"] is not None else len(canon),
            "distinct": len(set(canon)),
            "seconds": round(time.time() - t0, 3),
            "finished_at": utc_now_iso(),
        }

    def run(self, workers, merge_every=200, keep_shards=False):
        pending = [int(i) for i, s in self.state["cubes"].items()
                   if s["status"] in ("pending", "timeout")]
        pending.sort()
        total = self.config["n_cubes"]
        done = total - len(pending)
        self.log(f"resuming: {done}/{total} cubes already done; "
                 f"{len(pending)} to run on {workers} workers")
        if not pending:
            self.merge(keep_shards=keep_shards)
            return

        completed_since_merge = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(self._solve_cube, i): i for i in pending}
            for fut in as_completed(futs):
                i = futs[fut]
                try:
                    res = fut.result()
                except Exception as exc:  # keep the campaign alive
                    res = {"status": "error", "error": str(exc), "n_graphs": 0}
                self.state["cubes"][str(i)] = res
                done += 1
                completed_since_merge += 1
                if done % 25 == 0 or res["status"] != "done":
                    self.log(f"cube {i}: {res['status']} "
                             f"n_graphs={res.get('n_graphs')} "
                             f"({done}/{total})")
                self.save_state()
                if completed_since_merge >= merge_every:
                    self.merge(keep_shards=keep_shards)
                    completed_since_merge = 0
        self.merge(keep_shards=keep_shards)

    # --------------------------------------------------------------- merging
    def merge(self, keep_shards=False):
        """Merge all shard g6 into the deduped canonical union + DB diff."""
        with self._lock:
            campaign_tag = self.config.get("campaign_tag") or os.path.basename(self.dir)
            existing = _read_g6(self.canon_path)
            pool = set(existing)
            merged_shards = []
            for name in sorted(os.listdir(self.shards)):
                if not name.endswith(".g6"):
                    continue
                path = os.path.join(self.shards, name)
                pool.update(_read_g6(path))
                merged_shards.append(path)
            union = iso.dedup_graph6(sorted(pool)) if pool else []
            _atomic_write(self.canon_path, "\n".join(union) +
                          ("\n" if union else ""))
            write_graph_artifacts(
                union,
                self.canon_path,
                self.canon_jsonl_path,
                source="campaign",
                tag=campaign_tag,
            )
            if self.output_root:
                spec = SRGSpec(*self.config["params"])
                upsert_srg_catalog(
                    spec,
                    self.output_root,
                    union,
                    source="campaign",
                    tag=campaign_tag,
                )

            known = self._load_known()
            if known is not None:
                new = sorted(set(union) - known)
                _atomic_write(self.new_path, "\n".join(new) +
                              ("\n" if new else ""))
                self.log(f"merge: {len(union)} distinct; "
                         f"{len(union) - len(new)} known, {len(new)} NEW")
            else:
                self.log(f"merge: {len(union)} distinct graphs")

            if not keep_shards:  # disk rotation: compress merged shards
                for path in merged_shards:
                    with open(path, "rb") as src, \
                            gzip.open(path + ".gz", "wb") as dst:
                        dst.writelines(src)
                    os.remove(path)

    def _load_known(self):
        db = self.config.get("known_db")
        if not db or not os.path.exists(db):
            return None
        return set(_read_g6(db))

    # --------------------------------------------------------------- summary
    def summarize(self):
        campaign_tag = self.config.get("campaign_tag") or os.path.basename(self.dir)
        statuses = {}
        n_graphs = 0
        for s in self.state["cubes"].values():
            statuses[s["status"]] = statuses.get(s["status"], 0) + 1
            n_graphs += s.get("n_graphs", 0) or 0
        union = _read_g6(self.canon_path)
        complete = statuses.get("done", 0) == self.config["n_cubes"]
        elapsed = round(time.time() - self.state.get("started", time.time()), 3)
        finished_at = utc_now_iso()
        summary_path = os.path.join(self.dir, "summary.json")
        summary = {
            "schema_version": 2,
            "tag": campaign_tag,
            "srg_id": self.config.get("srg_id"),
            "params": self.config["params"],
            "campaign_dir": self.dir,
            "started_at": self.state.get("started_at"),
            "finished_at": finished_at,
            "seconds": elapsed,
            "n_cubes": self.config["n_cubes"],
            "cube_status": statuses,
            "search_complete": complete,
            "raw_models": n_graphs,
            "distinct_graphs": len(set(union)),
            "artifacts": {
                "summary_json": summary_path,
                "canonical_g6": self.canon_path,
                "canonical_jsonl": self.canon_jsonl_path,
                "new_candidates_g6": self.new_path,
                "state_json": self.state_path,
                "config_json": self.cfg_path,
                "cubes_txt": self.cubes_path,
                "formula_cnf": self.cnf_path,
            },
        }
        known = self._load_known()
        if known is not None:
            us = set(union)
            summary["known_reproduced"] = len(us & known)
            summary["new_beyond_known"] = len(us - known)
            summary["known_db_size"] = len(known)
        _atomic_write(summary_path, json.dumps(summary, indent=2))
        if self.output_root:
            spec = SRGSpec(*self.config["params"])
            update_srg_summary(
                spec,
                self.output_root,
                campaign_entry={
                    "tag": campaign_tag,
                    "campaign_dir": self.dir,
                    "search_complete": complete,
                    "distinct_graphs": len(set(union)),
                    "raw_models": n_graphs,
                    "seconds": elapsed,
                    "summary_json": summary_path,
                },
            )
        return summary


def _daemonize(log_path):
    """Double-fork + setsid so the campaign survives its launching shell."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    if os.fork() > 0:
        os._exit(0)          # original parent returns to the shell
    os.setsid()
    if os.fork() > 0:
        os._exit(0)          # first child exits; grandchild is the daemon
    sys.stdout.flush()
    sys.stderr.flush()
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    devnull = os.open(os.devnull, os.O_RDONLY)
    os.dup2(devnull, 0)


def _read_g6(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [ln.strip() for ln in fh if ln.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--v", type=int)
    ap.add_argument("--k", type=int)
    ap.add_argument("--lam", type=int)
    ap.add_argument("--mu", type=int)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", default="output",
                    help="output root directory (default: output)")
    ap.add_argument("--cube-cutoff", type=int, default=12,
                    help="smsg --simple-assignment-cutoff (cube granularity)")
    ap.add_argument("--cube-timeout", type=int, default=600,
                    help="per-cube smsg timeout in seconds")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--fix-clique", type=int, default=None,
                    help="anchor a K_t clique (max-clique staged decomposition)")
    ap.add_argument("--forbid-clique", type=int, default=None,
                    help="forbid K_t (e.g. 5 for SRG(37): omega<=4 stages)")
    ap.add_argument("--forbid-independent", type=int, default=None,
                    help="forbid an independent set of size t (coclique bound)")
    ap.add_argument("--known-db", default=None,
                    help="graph6 file of known graphs to diff against")
    ap.add_argument("--merge-every", type=int, default=200)
    ap.add_argument("--keep-shards", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--detach", action="store_true",
                    help="daemonize (double-fork + setsid) for long unattended "
                         "runs that survive the launching shell")
    args = ap.parse_args()

    output_root = resolve_output_root(_ROOT, args.out)
    has_all_params = all(x is not None for x in (args.v, args.k, args.lam, args.mu))
    has_any_params = any(x is not None for x in (args.v, args.k, args.lam, args.mu))
    if has_any_params and not has_all_params:
        raise ValueError("Specify all of --v/--k/--lam/--mu, or none of them.")
    spec = make_spec(args.v, args.k, args.lam, args.mu) if has_all_params else None

    if args.resume:
        if spec is not None:
            campaign_dir = campaign_path_for_spec(spec, output_root, args.tag)
            if not os.path.exists(os.path.join(campaign_dir, "config.json")):
                legacy = legacy_campaign_dir(_ROOT, args.tag)
                if os.path.exists(os.path.join(legacy, "config.json")):
                    campaign_dir = legacy
        else:
            candidates = discover_campaign_dirs(output_root, args.tag)
            legacy = legacy_campaign_dir(_ROOT, args.tag)
            if os.path.exists(os.path.join(legacy, "config.json")):
                candidates.append(legacy)
            if not candidates:
                raise FileNotFoundError(
                    f"No campaign found for tag '{args.tag}'. "
                    "Provide --v/--k/--lam/--mu to disambiguate or start a new campaign."
                )
            if len(candidates) > 1:
                msg = "\n".join(f"  - {p}" for p in sorted(candidates))
                raise RuntimeError(
                    f"Multiple campaigns found for tag '{args.tag}'. "
                    "Pass --v/--k/--lam/--mu to choose one.\n" + msg
                )
            campaign_dir = candidates[0]
    else:
        assert spec is not None, "new campaign needs --v/--k/--lam/--mu"
        campaign_dir = campaign_path_for_spec(spec, output_root, args.tag)

    if args.detach:
        _daemonize(os.path.join(campaign_dir, "daemon.out"))

    camp = Campaign(campaign_dir, output_root=output_root)

    if args.resume and os.path.exists(camp.cfg_path):
        camp.load()
        camp.log("=== RESUME ===")
    else:
        assert spec is not None, "new campaign needs --v/--k/--lam/--mu"
        encoder_opts = {}
        if args.fix_clique is not None:
            encoder_opts["fix_clique"] = args.fix_clique
        if args.forbid_clique is not None:
            encoder_opts["forbid_clique"] = args.forbid_clique
        if args.forbid_independent is not None:
            encoder_opts["forbid_independent"] = args.forbid_independent
        known_db = args.known_db
        if known_db is None and args.v == 37:
            kdir = os.path.join(_ROOT, "ProcessFiles", "known37")
            for name in ("switching_closure.g6", "all_canonical.g6"):
                cand = os.path.join(kdir, name)
                if os.path.exists(cand):
                    known_db = cand
                    break
        camp.init(spec, args.cube_cutoff, encoder_opts, args.cube_timeout,
                  known_db=known_db, campaign_tag=args.tag)
        camp.log("=== NEW CAMPAIGN ===")

    camp.run(args.workers, merge_every=args.merge_every,
             keep_shards=args.keep_shards)
    summary = camp.summarize()
    camp.log("=== SUMMARY ===\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
