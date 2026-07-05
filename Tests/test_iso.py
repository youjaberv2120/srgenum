"""Tests for graph6 I/O and nauty-based isomorph rejection."""

import itertools
import random

import pytest

import iso
from Utilities.paley import generate_paley_matrix


def _random_matrix(n, p=0.5, seed=0):
    rng = random.Random(seed)
    m = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < p:
                m[i][j] = m[j][i] = 1
    return m


@pytest.mark.parametrize("n", [1, 2, 5, 7, 10, 37])
def test_graph6_roundtrip(n):
    for seed in range(3):
        m = _random_matrix(n, seed=seed)
        g6 = iso.matrix_to_graph6(m)
        back = iso.graph6_to_matrix(g6)
        assert back == m


def test_canonical_form_idempotent():
    m = _random_matrix(9, seed=1)
    g6 = iso.matrix_to_graph6(m)
    c1 = iso.canonical_form(g6)
    c2 = iso.canonical_form(c1)
    assert c1 == c2


def test_relabelling_has_same_canonical_form():
    """A random permutation of the vertices must not change the canonical form."""
    n = 8
    m = _random_matrix(n, seed=2)
    perm = list(range(n))
    random.Random(5).shuffle(perm)
    pm = [[m[perm[i]][perm[j]] for j in range(n)] for i in range(n)]
    assert iso.canonical_form(iso.matrix_to_graph6(m)) == \
           iso.canonical_form(iso.matrix_to_graph6(pm))


def test_dedup_collapses_isomorphic_copies():
    """All labelled copies of one graph collapse to a single canonical graph."""
    n = 6
    base = _random_matrix(n, seed=3)
    g6s = []
    for perm in itertools.islice(itertools.permutations(range(n)), 40):
        pm = [[base[perm[i]][perm[j]] for j in range(n)] for i in range(n)]
        g6s.append(iso.matrix_to_graph6(pm))
    assert len(iso.dedup_graph6(g6s)) == 1


def test_paley37_roundtrip():
    P = generate_paley_matrix(37)
    assert iso.graph6_to_matrix(iso.matrix_to_graph6(P)) == P
