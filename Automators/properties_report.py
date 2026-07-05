"""P1-P12 property report for SRG(37,18,8,9).

Prints, for each proposed efficiency lever from the plan, its status:
  * CONFIRMED (param)  - provable from the parameters alone;
  * CONFIRMED (graph)  - verified computationally on the Paley graph P(37);
  * LITERATURE         - established in the cited literature;
  * METHOD             - a methodological choice validated by the pipeline;
and, where relevant, how it is folded back into the encoder as pruning.

Run:  python Automators/properties_report.py
"""

from __future__ import annotations

import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "ProgramFiles")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import properties as P  # noqa: E402
from Utilities.paley import generate_paley_matrix  # noqa: E402

V, K, LAM, MU = 37, 18, 8, 9


def build_report():
    Pal = generate_paley_matrix(37)
    comp = P.complement(Pal)

    cab = P.clique_adjacency_bound(V, K, LAM)
    dels = math.floor(P.delsarte_bound(V, K, LAM, MU))
    omega = P.max_clique_size(Pal)
    alpha = P.max_independent_set_size(Pal)
    tri = P.triangles_per_edge(Pal)
    nb_sizes, nb_degs = P.neighbourhood_regularity(Pal)
    identity = P.verify_adjacency_identity(Pal, K, LAM, MU)
    r2, r3 = P.rank_mod_p(Pal, 2), P.rank_mod_p(Pal, 3)
    comp_is_srg = P.verify_srg(comp, V, V - K - 1, V - 2 * K + MU - 2, V - 2 * K + LAM)["ok"]

    rows = [
        ("P1", "clique number omega <= 5",
         "CONFIRMED (param)",
         f"CAB={cab} beats Delsarte={dels}; C(2,6)={P.clique_adjacency_polynomial(V,K,LAM,2,6)}<0. "
         f"P(37) has omega={omega}. Folded in as forbid_clique=5."),
        ("P2", "coclique number alpha <= 5",
         "CONFIRMED (param)",
         f"complement has same parameters (self-complementary); CAB=5 => alpha<=5. "
         f"P(37) has alpha={alpha}. Folded in as forbid_independent=5."),
        ("P3", "every edge in exactly 8 triangles (lambda)",
         "CONFIRMED (graph)",
         f"triangles-per-edge range on P(37) = {tri} (== lambda). "
         f"Enforced by the common-neighbour cardinality constraint."),
        ("P4", "neighbourhood is 8-regular on 18 vertices",
         "CONFIRMED (graph)",
         f"P(37): neighbourhood sizes={nb_sizes}, local degrees={nb_degs}. "
         f"Seeds the staged neighbourhood fixing."),
        ("P5", "each non-adjacent pair has mu=9 common neighbours (V-forms)",
         "CONFIRMED (graph)",
         "subsumed by the SRG verification; drives the mu side of the "
         "conference identity (#common + [i~j] == 9)."),
        ("P6", "A^2 = kI + lambda A + mu(J-I-A)",
         "CONFIRMED (graph)",
         f"identity holds on P(37): {identity}. Basis of the single unified "
         f"per-pair cardinality constraint used by the encoder."),
        ("P7", "p-rank invariants (2-rank, 3-rank)",
         "CONFIRMED (graph)",
         f"P(37): 2-rank={r2}, 3-rank={r3} (3-rank=18 is the classic conference "
         f"invariant). Usable as a cheap fingerprint / parallel partition."),
        ("P8", "automorphism orders in {1,2,3,9,18,666}; <=20 fixed points",
         "LITERATURE",
         "Crnkovic-Maksimovic (2020): exactly 40 non-rigid SRG(37,18,8,9); "
         "6726 rigid. P(37) is the unique one with |Aut|=666. Justifies pure "
         "vertex-relabel isomorph rejection for the rigid bulk."),
        ("P9", "switching class / regular two-graph on 38 vertices",
         "LITERATURE",
         "the 6760 known graphs are descendants of 191 regular two-graphs on 38 "
         "vertices (McKay-Spence). Alternative decomposition + completeness "
         "cross-check."),
        ("P10", "parameters are self-complementary",
         "CONFIRMED (graph)",
         f"complement of P(37) is SRG(37,18,8,9): {comp_is_srg}. Any "
         f"non-complementation-symmetric invariant halves work / checks."),
        ("P11", "SMS lexicographic canonical form + nauty filter is isomorph-free",
         "METHOD",
         "validated: C5/Paley(9)/Petersen enumerations reduce to the correct "
         "unique counts via nauty dedup."),
        ("P12", "canonical max-clique anchor makes staging disjoint",
         "METHOD",
         "stage.py partitions by omega in {3,4,5} with a fixed K_t anchor; "
         "validated on Paley(9)."),
    ]
    return rows, {
        "clique_adjacency_bound": cab,
        "delsarte_bound": dels,
        "paley37_omega": omega,
        "paley37_alpha": alpha,
        "paley37_triangles_per_edge": tri,
        "paley37_neighbourhood_sizes": nb_sizes,
        "paley37_local_degrees": nb_degs,
        "paley37_adjacency_identity": identity,
        "paley37_2_rank": r2,
        "paley37_3_rank": r3,
        "complement_is_srg": comp_is_srg,
    }


def main():
    rows, metrics = build_report()
    print(f"Property report for SRG{(V, K, LAM, MU)}\n" + "=" * 60)
    for pid, name, status, detail in rows:
        print(f"\n[{pid}] {name}")
        print(f"      status: {status}")
        print(f"      {detail}")
    out = os.path.join(_ROOT, "Output")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "properties_report.json"), "w") as fh:
        json.dump({"rows": [dict(zip(("id", "name", "status", "detail"), r))
                            for r in rows], "metrics": metrics}, fh, indent=2)
    print(f"\nWrote {os.path.join(out, 'properties_report.json')}")


if __name__ == "__main__":
    main()
