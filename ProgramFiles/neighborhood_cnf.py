"""Backwards-compatible CNF generator (SUPERSEDED by srg_encoder.py).

The original implementation had two correctness bugs that this module no longer
carries:

* the degree constraint was applied only to seed vertices (3..n) rather than to
  all 37 vertices;
* the neighbourhoods of v1/v2 were fixed in an ad-hoc index order which is not a
  sound symmetry break.

This shim keeps the old entry point ``Run()`` (read ProcessFiles/graph.txt as a
seed, write ProcessFiles/formula.cnf) but routes it through the corrected,
SMS-compatible encoder in :mod:`srg_encoder`.  New code should use
``srg_encoder.add_srg_constraints`` and the pipeline in ``Automators/``.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from Utilities.graphReader import get_graph
from srg_encoder import CNFBuilder, add_srg_constraints, SRG_37


def Run(seed_path="ProcessFiles/graph.txt", out_path="ProcessFiles/formula.cnf"):
    seed = None
    if os.path.exists(seed_path):
        seed, *_ = get_graph(seed_path)

    builder = CNFBuilder(SRG_37.V)
    add_srg_constraints(builder, SRG_37, seed_matrix=seed)
    builder.to_dimacs(out_path)
    print(f"Wrote {out_path}: {builder.nvars} vars, {len(builder.clauses)} clauses")


if __name__ == "__main__":
    Run()
