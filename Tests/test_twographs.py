"""Tests for Seidel switching and two-graph utilities."""

import random

import twographs as tg
import properties as P
import iso
from Utilities.paley import generate_paley_matrix


def _rand(n, seed):
    rng = random.Random(seed)
    m = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < 0.5:
                m[i][j] = m[j][i] = 1
    return m


def test_switch_is_involution():
    G = _rand(9, 1)
    X = [0, 2, 5]
    assert tg.seidel_switch(tg.seidel_switch(G, X), X) == G


def test_switch_complement_equivalence():
    """Switching w.r.t. X and w.r.t. V\\X give the same graph."""
    n = 8
    G = _rand(n, 2)
    X = [1, 3, 4]
    comp = [v for v in range(n) if v not in X]
    assert tg.seidel_switch(G, X) == tg.seidel_switch(G, comp)


def test_seidel_matrix_values():
    G = [[0, 1, 0], [1, 0, 0], [0, 0, 0]]
    S = tg.seidel_matrix(G)
    assert S[0][1] == -1 and S[0][2] == 1 and S[1][2] == 1
    assert all(S[i][i] == 0 for i in range(3))


def test_paley37_extension_is_conference_two_graph():
    G = generate_paley_matrix(37)
    ext = tg.extend_isolated(G)
    assert tg.is_conference_two_graph(ext)
    ok, ab = tg.is_regular_two_graph(ext)
    assert ok and ab == (0, 37)


def test_descendant_at_isolated_vertex_returns_graph():
    G = generate_paley_matrix(37)
    ext = tg.extend_isolated(G)  # vertex 37 isolated
    back = tg.descendant(ext, 37)
    assert back == [list(r) for r in G]


def test_switching_family_members_are_srgs():
    G = generate_paley_matrix(37)
    fam = tg.switching_family_srg37(G)
    assert len(fam) >= 1
    for g6 in fam:
        assert P.verify_srg(iso.graph6_to_matrix(g6), 37, 18, 8, 9)["ok"]
