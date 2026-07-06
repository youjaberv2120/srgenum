"""SMS-compatible SAT encoder for strongly regular graphs.

This module produces a CNF whose *edge variables* follow exactly the numbering
convention used by SAT Modulo Symmetries (SMS / ``smsg``) and its Python
front-end PySMS: edges are numbered ``1 .. C(n,2)`` in ``combinations(range(n),
2)`` order, i.e. (0,1), (0,2), ..., (0,n-1), (1,2), ...  Auxiliary variables
(common-neighbour indicators and cardinality-counter registers) come after the
edge block.  Keeping this layout means the very same DIMACS file can be handed
either to the standalone ``cadical`` binary / PySAT, or to ``smsg --dimacs``.

Correctness fixes over the original ``neighborhood_cnf.py``:

* Degree ``k`` is enforced on **all** vertices, not just the seed vertices.
* Every pair (i, j) gets the full common-neighbour constraint, encoded once and
  unconditionally using the *conference-graph identity*

      (# common neighbours of i, j) + [i ~ j] == mu          (when mu = lam + 1)

  which holds for SRG(37,18,8,9) because it is a conference graph
  (mu - lam = 1).  For general parameters the classic guarded encoding
  (adjacent -> lam, non-adjacent -> mu) is used instead.
* The common-neighbour indicator a(i,j,k) is fully defined:
  a <-> e(i,k) AND e(j,k).
"""

from __future__ import annotations

from itertools import combinations
from typing import Iterable, NamedTuple, Optional, Sequence, List


class SRGSpec(NamedTuple):
    """Parameters (v, k, lambda, mu) of a strongly regular graph."""

    V: int
    degree: int
    lam: int
    mu: int

    @property
    def is_conference(self) -> bool:
        """Type-I / conference parameters: k=(v-1)/2, lam=(v-5)/4, mu=(v-1)/4."""
        v = self.V
        return (
            self.degree * 2 == v - 1
            and self.lam * 4 == v - 5
            and self.mu * 4 == v - 1
        )


SRG_37 = SRGSpec(37, 18, 8, 9)


def make_spec(v: int, k: int, lam: int, mu: int) -> SRGSpec:
    """Build an :class:`SRGSpec` after basic parameter-algebra checks."""
    from properties import validate_srg_parameters

    validate_srg_parameters(v, k, lam, mu)
    return SRGSpec(v, k, lam, mu)


class CNFBuilder:
    """Minimal engine-agnostic CNF accumulator.

    Exposes the small interface the encoder relies on (``var_edge``,
    ``new_var``, ``add_clause``) so the exact same encoding routines work either
    on this builder or on a PySMS ``GraphEncodingBuilder`` (see
    :class:`PySMSBuilder`).
    """

    def __init__(self, n: int):
        self.n = n
        self._edge = [[0] * n for _ in range(n)]
        self._nvars = 0
        self.clauses: List[List[int]] = []
        # Reserve the edge variables first, in SMS/PySMS order.
        for u, v in combinations(range(n), 2):
            self._nvars += 1
            self._edge[u][v] = self._edge[v][u] = self._nvars

    def var_edge(self, u: int, v: int) -> int:
        return self._edge[u][v]

    def new_var(self) -> int:
        self._nvars += 1
        return self._nvars

    def add_clause(self, clause: Iterable[int]) -> None:
        self.clauses.append(list(clause))

    @property
    def nvars(self) -> int:
        return self._nvars

    def to_dimacs(self, path: str) -> None:
        with open(path, "w") as fh:
            fh.write(f"p cnf {self._nvars} {len(self.clauses)}\n")
            for cl in self.clauses:
                fh.write(" ".join(map(str, cl)) + " 0\n")


# --------------------------------------------------------------------------- #
# Cardinality encodings (Sinz sequential counter).                            #
# --------------------------------------------------------------------------- #
def _at_most_k(builder, lits: Sequence[int], k: int) -> None:
    """Encode sum(lits) <= k using the Sinz (2005) sequential counter."""
    n = len(lits)
    if k >= n:
        return
    if k <= 0:
        for x in lits:
            builder.add_clause([-x])
        return
    # register s[i][j], i in 0..n-2, j in 0..k-1
    s = [[builder.new_var() for _ in range(k)] for _ in range(n - 1)]
    builder.add_clause([-lits[0], s[0][0]])
    for j in range(1, k):
        builder.add_clause([-s[0][j]])
    for i in range(1, n - 1):
        builder.add_clause([-lits[i], s[i][0]])
        builder.add_clause([-s[i - 1][0], s[i][0]])
        for j in range(1, k):
            builder.add_clause([-lits[i], -s[i - 1][j - 1], s[i][j]])
            builder.add_clause([-s[i - 1][j], s[i][j]])
        builder.add_clause([-lits[i], -s[i - 1][k - 1]])
    builder.add_clause([-lits[n - 1], -s[n - 2][k - 1]])


def _at_least_k(builder, lits: Sequence[int], k: int) -> None:
    """Encode sum(lits) >= k  <=>  sum(not lits) <= len - k."""
    n = len(lits)
    if k <= 0:
        return
    if k > n:
        builder.add_clause([])  # unsatisfiable
        return
    _at_most_k(builder, [-x for x in lits], n - k)


def _exactly_k(builder, lits: Sequence[int], k: int) -> None:
    _at_least_k(builder, lits, k)
    _at_most_k(builder, lits, k)


def _guarded_exactly_k(builder, guard: int, lits: Sequence[int], k: int) -> None:
    """Encode  guard -> (sum(lits) == k)  by prefixing every clause with -guard.

    The auxiliary counter variables are private to this call, so guarding two
    different bounds with complementary guards is sound.
    """
    tmp = _ClauseSpy(builder)
    _exactly_k(tmp, lits, k)
    for cl in tmp.captured:
        builder.add_clause([-guard] + cl)


class _ClauseSpy:
    """Wraps a builder so cardinality clauses can be captured and re-emitted
    with a guard literal, while still drawing fresh variables from the real
    builder."""

    def __init__(self, real):
        self._real = real
        self.captured: List[List[int]] = []

    def new_var(self) -> int:
        return self._real.new_var()

    def add_clause(self, clause) -> None:
        self.captured.append(list(clause))


# --------------------------------------------------------------------------- #
# SRG constraints.                                                             #
# --------------------------------------------------------------------------- #
def add_srg_constraints(
    builder,
    spec: SRGSpec = SRG_37,
    *,
    seed_matrix: Optional[Sequence[Sequence[int]]] = None,
    fix_clique: int = 0,
    forbid_clique: Optional[int] = None,
    forbid_independent: Optional[int] = None,
) -> dict:
    """Add all SRG(v,k,lam,mu) constraints to ``builder``.

    :param seed_matrix: optional m x m 0/1 adjacency matrix fixing the induced
        subgraph on vertices 0..m-1 (units on edge variables).
    :param fix_clique: if > 0, force vertices 0..fix_clique-1 to be a clique
        (units).  Used by the multi-stage max-clique anchor decomposition.
    :param forbid_clique: if set, forbid cliques of size > forbid_clique
        (clique bound; for (37,18,8,9) use 5).  WARNING: C(n, t+1) clauses.
    :param forbid_independent: if set, forbid independent sets of size >
        this value (coclique bound; for (37,18,8,9) use 5).

    Returns metadata describing the SMS initial partition to use.
    """
    n = spec.V

    def E(u, v):
        return builder.var_edge(u, v)

    # ---- seed / anchor fixing ------------------------------------------- #
    if seed_matrix is not None:
        m = len(seed_matrix)
        for i in range(m):
            for j in range(i + 1, m):
                lit = E(i, j)
                builder.add_clause([lit] if seed_matrix[i][j] else [-lit])

    if fix_clique and fix_clique > 1:
        for i, j in combinations(range(fix_clique), 2):
            builder.add_clause([E(i, j)])

    # ---- degree: every vertex has exactly k neighbours ------------------ #
    for u in range(n):
        _exactly_k(builder, [E(u, w) for w in range(n) if w != u], spec.degree)

    # ---- common-neighbour indicators a(i,j,k) <-> E(i,k) & E(j,k) ------- #
    # Stored so the count constraint can reuse them.
    for i, j in combinations(range(n), 2):
        a_lits = []
        for k in range(n):
            if k == i or k == j:
                continue
            a = builder.new_var()
            builder.add_clause([-a, E(i, k)])
            builder.add_clause([-a, E(j, k)])
            builder.add_clause([-E(i, k), -E(j, k), a])
            a_lits.append(a)

        if spec.mu == spec.lam + 1:
            # Conference identity: #common(i,j) + [i~j] == mu, unconditionally.
            _exactly_k(builder, a_lits + [E(i, j)], spec.mu)
        else:
            # General SRG: adjacent -> lam common, non-adjacent -> mu common.
            _guarded_exactly_k(builder, E(i, j), a_lits, spec.lam)
            _guarded_exactly_k(builder, -E(i, j), a_lits, spec.mu)

    # ---- optional clique / coclique bounds ------------------------------ #
    if forbid_clique is not None:
        t = forbid_clique + 1
        for S in combinations(range(n), t):
            builder.add_clause([-E(a, b) for a, b in combinations(S, 2)])

    if forbid_independent is not None:
        t = forbid_independent + 1
        for S in combinations(range(n), t):
            builder.add_clause([E(a, b) for a, b in combinations(S, 2)])

    # ---- SMS initial partition ------------------------------------------ #
    # A regular graph is fully vertex-transitive at the constraint level, so all
    # vertices start in one cell.  A fixed anchor freezes the first cells.
    anchor = max(fix_clique, len(seed_matrix) if seed_matrix is not None else 0)
    if 0 < anchor < n:
        partition = " ".join(["1"] * anchor + [str(n - anchor)])
    elif anchor >= n:
        partition = " ".join(["1"] * n)
    else:
        partition = str(n)

    return {"initial_partition": partition, "num_edge_vars": n * (n - 1) // 2}


def edge_var_count(n: int) -> int:
    return n * (n - 1) // 2


# --------------------------------------------------------------------------- #
# Optional PySMS adapter (only used when the SMS build is available).          #
# --------------------------------------------------------------------------- #
class PySMSBuilder:
    """Adapter presenting the CNFBuilder interface on top of a PySMS
    ``GraphEncodingBuilder``.  Import of PySMS is done lazily by the caller."""

    def __init__(self, geb):
        self._g = geb
        self.n = geb.n

    def var_edge(self, u: int, v: int) -> int:
        return self._g.var_edge(u, v)

    def new_var(self) -> int:
        return self._g.id()

    def add_clause(self, clause) -> None:
        self._g.append(list(clause))
