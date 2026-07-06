"""Structural invariants for SRG(37,18,8,9): the P1-P12 checks from the plan.

Everything here is pure Python (no numpy) so it runs in the project venv as-is.
These routines serve two purposes:

* validation - confirm a produced / downloaded graph really is SRG(v,k,lam,mu);
* property lab - compute the invariants (clique/coclique numbers, p-ranks,
  clique-adjacency bound, complement) that the plan proposes as efficiency
  levers, so they can be confirmed empirically before being folded back into
  the encoder as pruning.
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Dict, List, Optional, Sequence

Matrix = Sequence[Sequence[int]]


# --------------------------------------------------------------------------- #
# Parameter algebra (necessary, not sufficient — catches typos early)            #
# --------------------------------------------------------------------------- #
def validate_srg_parameters(v: int, k: int, lam: int, mu: int) -> None:
    """Check basic algebraic necessary conditions on SRG(v, k, lam, mu).

    These are **not** sufficient for existence, but reject most typos before
    a long encode/enumerate run.  Raises :class:`ValueError` on failure.
    """
    errors: List[str] = []

    if v < 3:
        errors.append(f"v={v}: need at least 3 vertices")
    for name, val in (("k", k), ("lam", lam), ("mu", mu)):
        if val < 0:
            errors.append(f"{name}={val}: must be non-negative")
    if k >= v:
        errors.append(f"k={k} must satisfy k < v={v}")
    if lam > k:
        errors.append(f"lam={lam} must satisfy lam <= k={k}")
    if mu > k:
        errors.append(f"mu={mu} must satisfy mu <= k={k}")

    if (v * k) % 2:
        errors.append(f"v*k={v * k} must be even (handshaking lemma)")
    if (v * k * (k - 1)) % 2:
        errors.append(f"v*k*(k-1) must be even")

    lhs = k * (k - 1 - lam)
    rhs = mu * (v - k - 1)
    if lhs != rhs:
        errors.append(
            f"counting identity: k(k-1-lam)={lhs} != mu(v-k-1)={rhs}"
        )

    k_bar = v - k - 1
    lam_bar = v - 2 - 2 * k + mu
    mu_bar = v - 2 * k + lam
    if k_bar >= 0 and lam_bar >= 0 and mu_bar >= 0:
        lhs_c = k_bar * (k_bar - 1 - lam_bar)
        rhs_c = mu_bar * (v - k_bar - 1)
        if lhs_c != rhs_c:
            errors.append(
                "complement counting identity failed for "
                f"(k'={k_bar}, lam'={lam_bar}, mu'={mu_bar}): "
                f"k'(k'-1-lam')={lhs_c} != mu'(v-k'-1)={rhs_c}"
            )

    disc = (lam - mu) ** 2 + 4 * (k - mu)
    if disc < 0:
        errors.append(
            f"eigenvalue discriminant (lam-mu)^2+4(k-mu)={disc} is negative"
        )
    else:
        _, r, s = eigenvalues(v, k, lam, mu)
        if abs(r - s) < 1e-12:
            if (v - 1) % 2:
                errors.append(
                    f"discriminant zero requires v-1={v - 1} to be even "
                    "for integer eigenvalue multiplicities"
                )
        else:
            f = (-(v - 1) * s - k) / (r - s)
            g = (v - 1) - f
            for name, mult in (("f", f), ("g", g)):
                if mult < -1e-9:
                    errors.append(
                        f"eigenvalue multiplicity {name}={mult:.6f} is negative"
                    )
                elif abs(mult - round(mult)) > 1e-6:
                    errors.append(
                        f"eigenvalue multiplicity {name}={mult:.6f} "
                        "is not an integer"
                    )

    if errors:
        raise ValueError(
            "SRG parameter checks failed for "
            f"SRG({v},{k},{lam},{mu}):\n  - " + "\n  - ".join(errors)
        )


# --------------------------------------------------------------------------- #
# Basic SRG verification                                                        #
# --------------------------------------------------------------------------- #
def verify_srg(matrix: Matrix, v: int, k: int, lam: int, mu: int) -> Dict[str, object]:
    """Check that ``matrix`` is an SRG(v,k,lam,mu).  Returns a report dict."""
    n = len(matrix)
    report: Dict[str, object] = {"ok": True, "errors": []}

    if n != v:
        report["ok"] = False
        report["errors"].append(f"vertex count {n} != {v}")
        return report

    for i in range(n):
        deg = sum(matrix[i])
        if deg != k:
            report["ok"] = False
            report["errors"].append(f"vertex {i} has degree {deg} != {k}")
            break

    for i in range(n):
        for j in range(i + 1, n):
            common = sum(1 for w in range(n) if matrix[i][w] and matrix[j][w])
            want = lam if matrix[i][j] else mu
            if common != want:
                report["ok"] = False
                report["errors"].append(
                    f"pair ({i},{j}) {'adj' if matrix[i][j] else 'non-adj'} "
                    f"has {common} common neighbours, want {want}"
                )
                break
        if not report["ok"]:
            break
    return report


def complement(matrix: Matrix) -> List[List[int]]:
    n = len(matrix)
    return [[0 if i == j else 1 - matrix[i][j] for j in range(n)] for i in range(n)]


# --------------------------------------------------------------------------- #
# P1 - clique adjacency bound (Greaves-Soicher)                                 #
# --------------------------------------------------------------------------- #
def clique_adjacency_polynomial(v: int, k: int, lam: int, x: int, y: int) -> int:
    """C_G(x,y) = x(x+1)(v-y) - 2xy(k-y+1) + y(y-1)(lam-y+2)."""
    return x * (x + 1) * (v - y) - 2 * x * y * (k - y + 1) + y * (y - 1) * (lam - y + 2)


def clique_adjacency_bound(v: int, k: int, lam: int, max_c: int = 40) -> int:
    """Least clique size ruled out; omega(G) < that value.

    Returns the clique-adjacency bound (an upper bound on omega): the smallest
    c >= 2 such that C(b, c+1) < 0 for some integer b.
    """
    for c in range(2, max_c):
        y = c + 1
        # C is a downward parabola in x; scan a small window around its apex.
        for b in range(-1, v + 2):
            if clique_adjacency_polynomial(v, k, lam, b, y) < 0:
                return c
    return max_c


def delsarte_bound(v: int, k: int, lam: int, mu: int) -> float:
    """1 - k/s where s is the least eigenvalue."""
    s = least_eigenvalue(v, k, lam, mu)
    return 1 - k / s


# --------------------------------------------------------------------------- #
# Spectrum (from parameters; exact where rational, else float)                  #
# --------------------------------------------------------------------------- #
def eigenvalues(v: int, k: int, lam: int, mu: int):
    """Return (k, r, s) as floats; r > s are the restricted eigenvalues."""
    disc = (lam - mu) ** 2 + 4 * (k - mu)
    root = math.sqrt(disc)
    r = ((lam - mu) + root) / 2
    s = ((lam - mu) - root) / 2
    return float(k), r, s


def least_eigenvalue(v: int, k: int, lam: int, mu: int) -> float:
    return eigenvalues(v, k, lam, mu)[2]


def eigenvalue_multiplicities(v: int, k: int, lam: int, mu: int):
    """Multiplicities (1, f, g) of (k, r, s).  For conference graphs f = g."""
    _, r, s = eigenvalues(v, k, lam, mu)
    f = (-(v - 1) * s - k) / (r - s) if r != s else (v - 1) / 2
    g = (v - 1) - f
    return 1, round(f, 6), round(g, 6)


# --------------------------------------------------------------------------- #
# Clique / coclique numbers                                                     #
# --------------------------------------------------------------------------- #
def max_clique_size(matrix: Matrix, cap: Optional[int] = None) -> int:
    """Size of a maximum clique (optionally capped for early exit).

    Bron-Kerbosch with pivoting; fine for SRG(37,...) whose cliques are tiny.
    """
    n = len(matrix)
    adj = [set(j for j in range(n) if matrix[i][j]) for i in range(n)]
    best = 0

    def expand(R: int, P: set, X: set):
        nonlocal best
        if not P and not X:
            best = max(best, R)
            return
        if cap is not None and best >= cap:
            return
        # bound: R + |P| can't beat best
        if R + len(P) <= best:
            return
        pivot = max(P | X, key=lambda u: len(adj[u] & P)) if (P | X) else None
        candidates = list(P - adj[pivot]) if pivot is not None else list(P)
        for v in candidates:
            expand(R + 1, P & adj[v], X & adj[v])
            P = P - {v}
            X = X | {v}

    expand(0, set(range(n)), set())
    return best


def contains_clique(matrix: Matrix, t: int) -> bool:
    return max_clique_size(matrix, cap=t) >= t


def max_independent_set_size(matrix: Matrix, cap: Optional[int] = None) -> int:
    return max_clique_size(complement(matrix), cap=cap)


# --------------------------------------------------------------------------- #
# P7 - p-rank of the adjacency matrix                                           #
# --------------------------------------------------------------------------- #
def rank_mod_p(matrix: Matrix, p: int, add_identity: bool = False) -> int:
    """Rank over GF(p) of A (or A + I) by Gaussian elimination."""
    n = len(matrix)
    M = [[(matrix[i][j] + (1 if add_identity and i == j else 0)) % p
          for j in range(n)] for i in range(n)]
    rank = 0
    col = 0
    for col in range(n):
        pivot = None
        for r in range(rank, n):
            if M[r][col] % p != 0:
                pivot = r
                break
        if pivot is None:
            continue
        M[rank], M[pivot] = M[pivot], M[rank]
        inv = pow(M[rank][col], p - 2, p) if p > 2 else 1
        M[rank] = [(val * inv) % p for val in M[rank]]
        for r in range(n):
            if r != rank and M[r][col] % p != 0:
                factor = M[r][col]
                M[r] = [(M[r][c] - factor * M[rank][c]) % p for c in range(n)]
        rank += 1
    return rank


# --------------------------------------------------------------------------- #
# P3 - triangles / V-forms per edge                                            #
# --------------------------------------------------------------------------- #
def triangles_per_edge(matrix: Matrix):
    """Return (min, max) number of triangles on an edge (= common neighbours of
    its endpoints).  For an SRG this should be exactly lambda on every edge."""
    n = len(matrix)
    lo, hi = None, None
    for i in range(n):
        for j in range(i + 1, n):
            if not matrix[i][j]:
                continue
            t = sum(1 for w in range(n) if matrix[i][w] and matrix[j][w])
            lo = t if lo is None else min(lo, t)
            hi = t if hi is None else max(hi, t)
    return lo, hi


# --------------------------------------------------------------------------- #
# P4 - local graph (neighbourhood) regularity                                  #
# --------------------------------------------------------------------------- #
def neighbourhood_regularity(matrix: Matrix):
    """For each vertex, examine the induced subgraph on its neighbours.

    Returns (neighbourhood_sizes, local_degrees) as sorted unique tuples.  For
    SRG(37,18,8,9) every neighbourhood is an 8-regular graph on 18 vertices.
    """
    n = len(matrix)
    sizes = set()
    local_degs = set()
    for v in range(n):
        nb = [u for u in range(n) if matrix[v][u]]
        sizes.add(len(nb))
        for u in nb:
            local_degs.add(sum(1 for w in nb if matrix[u][w]))
    return tuple(sorted(sizes)), tuple(sorted(local_degs))


# --------------------------------------------------------------------------- #
# P6 - adjacency identity A^2 = kI + lam A + mu (J - I - A)                     #
# --------------------------------------------------------------------------- #
def verify_adjacency_identity(matrix: Matrix, k: int, lam: int, mu: int) -> bool:
    n = len(matrix)
    for i in range(n):
        row_i = matrix[i]
        for j in range(n):
            a2 = sum(row_i[w] * matrix[w][j] for w in range(n))
            if i == j:
                want = k
            elif matrix[i][j]:
                want = lam
            else:
                want = mu
            if a2 != want:
                return False
    return True


# --------------------------------------------------------------------------- #
# Aggregate report                                                              #
# --------------------------------------------------------------------------- #
def full_report(matrix: Matrix, v: int = 37, k: int = 18, lam: int = 8,
                mu: int = 9) -> Dict[str, object]:
    srg = verify_srg(matrix, v, k, lam, mu)
    return {
        "is_srg": srg["ok"],
        "srg_errors": srg["errors"],
        "omega": max_clique_size(matrix),
        "alpha": max_independent_set_size(matrix),
        "clique_adjacency_bound": clique_adjacency_bound(v, k, lam),
        "delsarte_bound": round(delsarte_bound(v, k, lam, mu), 4),
        "eigenvalues": tuple(round(x, 4) for x in eigenvalues(v, k, lam, mu)),
        "multiplicities": eigenvalue_multiplicities(v, k, lam, mu),
        "2_rank": rank_mod_p(matrix, 2),
        "3_rank": rank_mod_p(matrix, 3),
    }


if __name__ == "__main__":
    # Confirm P1/P2 at the parameter level (no graph required).
    v, k, lam, mu = 37, 18, 8, 9
    print(f"SRG{(v, k, lam, mu)} conference graph: "
          f"{k*2 == v-1 and lam*4 == v-5 and mu*4 == v-1}")
    print(f"Delsarte clique bound  : omega <= {math.floor(delsarte_bound(v,k,lam,mu))}")
    print(f"Clique adjacency bound : omega <= {clique_adjacency_bound(v,k,lam)}")
    print(f"C(2,6) = {clique_adjacency_polynomial(v,k,lam,2,6)}  (<0 => no K6)")
    print(f"eigenvalues (k,r,s)    : {tuple(round(x,4) for x in eigenvalues(v,k,lam,mu))}")
    print(f"multiplicities (1,f,g) : {eigenvalue_multiplicities(v,k,lam,mu)}")
