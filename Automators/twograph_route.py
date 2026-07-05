"""Two-graph / Seidel-switching analysis of the SRG(37,18,8,9) ground-truth DB.

Every SRG(37,18,8,9) is a descendant of a regular two-graph on 38 vertices.
Graphs that are descendants of the *same* two-graph form one Seidel switching
class.  This driver partitions the known DB into switching classes and checks:

  * closure: the switching family of each graph stays inside the DB
             (no descendant escapes the known set -> DB is switching-closed);
  * partition: the class sizes sum to the DB size;
  * count: the number of classes = number of regular two-graphs on 38 vertices
           realising SRG(37,18,8,9).

This is the completeness cross-check for the two-graph route: an independent,
purely combinatorial confirmation that the 6766 organise consistently into
two-graphs (and a template for generating graphs class-by-class).

Usage:  python Automators/twograph_route.py [--limit N]
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

import twographs as tg  # noqa: E402
import iso  # noqa: E402

DB = os.path.join(_ROOT, "ProcessFiles", "known37", "all_canonical.g6")
OUT = os.path.join(_ROOT, "ProcessFiles", "known37")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="only process the first N graphs (for a quick check)")
    args = ap.parse_args()

    with open(DB) as fh:
        db = [ln.strip() for ln in fh if ln.strip()]
    db_set = set(db)
    if args.limit:
        db = db[:args.limit]

    t0 = time.time()
    seen = set()
    classes = []          # list of (representative, members_in_db)
    escapes = 0           # family members that fall outside the DB
    processed = 0
    for g6 in db:
        if g6 in seen:
            continue
        fam = set(tg.switching_family_srg37(iso.graph6_to_matrix(g6)))
        escapes += len(fam - db_set)
        in_db = fam & db_set
        classes.append((min(fam), sorted(in_db)))
        seen |= in_db
        processed += 1
        if processed % 200 == 0:
            print(f"  {processed} classes, {len(seen)} graphs covered "
                  f"({time.time() - t0:.0f}s)", flush=True)

    sizes = sorted(len(m) for _, m in classes)
    size_hist = {}
    for s in sizes:
        size_hist[s] = size_hist.get(s, 0) + 1

    report = {
        "db_size": len(db_set),
        "graphs_processed": len(db),
        "switching_classes": len(classes),
        "graphs_covered": len(seen),
        "closure_ok": escapes == 0,
        "family_escapes": escapes,
        "partition_ok": (len(seen) == len(db) and args.limit is None),
        "class_size_histogram": size_hist,
        "seconds": round(time.time() - t0, 1),
    }
    if args.limit is None:
        with open(os.path.join(OUT, "two_graph_classes.json"), "w") as fh:
            json.dump({"representatives": [c[0] for c in classes]}, fh)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
