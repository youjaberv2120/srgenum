"""Seidel switching and two-graph utilities for the SRG(37,18,8,9) route.

Background (the completeness route the campaign follows):

  * The **Seidel matrix** of a graph G is S = J - I - 2A (entries: 0 on the
    diagonal, -1 for adjacent pairs, +1 for non-adjacent pairs).
  * **Seidel switching** w.r.t. a vertex set X toggles adjacency across the cut
    (X, V\\X).  The switching class of G is a **two-graph**.
  * A two-graph is **regular** iff its Seidel matrix has exactly two distinct
    eigenvalues; a **conference** two-graph on m vertices satisfies S^2 = (m-1)I.
  * SRG(37,18,8,9) satisfies k = 2*mu (18 = 2*9), so adjoining an isolated
    vertex to any such graph yields a graph on 38 vertices whose switching class
    is a regular (conference) two-graph, and *every* descendant of that
    two-graph is again an SRG(37,18,8,9).  Enumerating regular two-graphs on 38
    vertices and taking descendants is the classical route to the 6760/6766.

These utilities let us (a) move within a switching class, (b) test regularity,
and (c) generate the whole switching-class family of SRG(37) graphs from one
member -- used both to cross-check the ground-truth DB (closure) and to expand
seeds during enumeration.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence

import iso

Matrix = List[List[int]]


# --------------------------------------------------------------------------- #
# Seidel matrix / switching.                                                   #
# --------------------------------------------------------------------------- #
def seidel_matrix(A: Sequence[Sequence[int]]) -> Matrix:
    """S = J - I - 2A: 0 on diagonal, -1 if adjacent, +1 if non-adjacent."""
    n = len(A)
    S = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                S[i][j] = 0
            else:
                S[i][j] = -1 if A[i][j] else 1
    return S


def seidel_switch(A: Sequence[Sequence[int]], X: Iterable[int]) -> Matrix:
    """Return the graph obtained by Seidel switching G w.r.t. vertex set X."""
    n = len(A)
    Xs = set(X)
    B = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            across = (i in Xs) ^ (j in Xs)
            bit = (1 - A[i][j]) if across else A[i][j]
            B[i][j] = B[j][i] = bit
    return B


def _matmul(A, B):
    n, m, p = len(A), len(B), len(B[0])
    out = [[0] * p for _ in range(n)]
    for i in range(n):
        Ai = A[i]
        for k in range(m):
            a = Ai[k]
            if a:
                Bk = B[k]
                Oi = out[i]
                for j in range(p):
                    Oi[j] += a * Bk[j]
    return out


# --------------------------------------------------------------------------- #
# Two-graph regularity.                                                        #
# --------------------------------------------------------------------------- #
def is_regular_two_graph(A: Sequence[Sequence[int]]):
    """Return (is_regular, (a, b)) where S^2 = a*S + b*I for a regular two-graph.

    Uses only integer arithmetic: the diagonal of S^2 is constant (= m-1) giving
    b, and every off-diagonal S2[i][j] must equal a*S[i][j] for a single a.
    """
    S = seidel_matrix(A)
    m = len(S)
    S2 = _matmul(S, S)
    b = S2[0][0]
    for i in range(m):
        if S2[i][i] != b:
            return False, None
    a = None
    for i in range(m):
        for j in range(m):
            if i == j:
                continue
            if S[i][j] == 0:
                if S2[i][j] != 0:
                    return False, None
                continue
            ratio = S2[i][j] / S[i][j]
            if a is None:
                a = ratio
            elif ratio != a:
                return False, None
    a = 0 if a is None else int(a)
    return True, (a, b)


def is_conference_two_graph(A: Sequence[Sequence[int]]) -> bool:
    """Conference two-graph on m vertices: S^2 = (m-1) I (a, b) = (0, m-1)."""
    ok, ab = is_regular_two_graph(A)
    return ok and ab == (0, len(A) - 1)


# --------------------------------------------------------------------------- #
# Descendants.                                                                 #
# --------------------------------------------------------------------------- #
def descendant(A: Sequence[Sequence[int]], v: int) -> Matrix:
    """Descendant of the two-graph at vertex v: switch to isolate v, delete v."""
    n = len(A)
    nbrs = [u for u in range(n) if A[v][u]]
    B = seidel_switch(A, nbrs)  # isolates v (v now adjacent to nobody)
    keep = [u for u in range(n) if u != v]
    return [[B[i][j] for j in keep] for i in keep]


def extend_isolated(A: Sequence[Sequence[int]]) -> Matrix:
    """Adjoin one isolated vertex (index n) to G."""
    n = len(A)
    B = [[0] * (n + 1) for _ in range(n + 1)]
    for i in range(n):
        for j in range(n):
            B[i][j] = A[i][j]
    return B


def switching_family_srg37(A: Sequence[Sequence[int]]) -> List[str]:
    """From one SRG(37,18,8,9) graph, return the canonical graph6 forms of the
    whole switching-class family (descendants of the 38-vertex two-graph).

    Requires k = 2*mu (true for (37,18,8,9)); the 38-vertex extension is a
    conference two-graph and all 38 descendants are SRG(37,18,8,9).
    """
    ext = extend_isolated(A)  # 38 vertices, last one isolated
    fam = [iso.matrix_to_graph6(descendant(ext, v)) for v in range(len(ext))]
    return list(dict.fromkeys(iso.canonical_forms(fam)))
