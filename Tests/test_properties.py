"""Tests for the P1-P12 invariant computations."""

import properties as P
from Utilities.paley import generate_paley_matrix


def test_clique_adjacency_bound_37():
    # Delsarte gives 6, the clique adjacency bound gives 5.
    assert P.clique_adjacency_bound(37, 18, 8) == 5
    assert P.clique_adjacency_polynomial(37, 18, 8, 2, 6) == -6


def test_paley37_is_srg():
    P37 = generate_paley_matrix(37)
    assert P.verify_srg(P37, 37, 18, 8, 9)["ok"]


def test_paley37_invariants():
    P37 = generate_paley_matrix(37)
    assert P.max_clique_size(P37) == 4
    assert P.max_independent_set_size(P37) == 4
    assert P.rank_mod_p(P37, 3) == 18          # classic conference 3-rank
    assert P.triangles_per_edge(P37) == (8, 8)  # every edge in exactly lambda
    assert P.neighbourhood_regularity(P37) == ((18,), (8,))
    assert P.verify_adjacency_identity(P37, 18, 8, 9)


def test_complement_involution_and_self_complementary_params():
    P37 = generate_paley_matrix(37)
    cc = P.complement(P.complement(P37))
    assert cc == [list(row) for row in P37]
    comp = P.complement(P37)
    # complement parameters of (37,18,8,9) are again (37,18,8,9)
    assert P.verify_srg(comp, 37, 18, 8, 9)["ok"]


def test_verify_srg_rejects_perturbation():
    P37 = generate_paley_matrix(37)
    P37[0][1] = P37[1][0] = 1 - P37[0][1]
    assert not P.verify_srg(P37, 37, 18, 8, 9)["ok"]


def test_petersen_invariants():
    # Petersen = SRG(10,3,0,1), triangle-free, independence number 4.
    pet = P.complement(_triangular_T5())
    assert P.verify_srg(pet, 10, 3, 0, 1)["ok"]
    assert P.max_clique_size(pet) == 2  # triangle-free


def _triangular_T5():
    """Johnson graph T(5) = SRG(10,6,3,4); its complement is the Petersen graph."""
    import itertools
    verts = list(itertools.combinations(range(5), 2))
    n = len(verts)
    m = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if set(verts[i]) & set(verts[j]):
                m[i][j] = m[j][i] = 1
    return m
