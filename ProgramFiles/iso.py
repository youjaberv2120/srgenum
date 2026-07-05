"""Isomorph rejection via nauty (graph6 + labelg / shortg).

SMS performs *complete* symmetry breaking only on fully-defined graphs; the
standard practice (Kirchweger & Szeider) is to run a light canonical filter on
the produced models.  When SMS is unavailable and we enumerate with a plain SAT
backend, this canonical filter is what makes the output isomorph-free.

This module implements graph6 I/O in pure Python (so it works even without the
nauty ``amtog`` converter) and shells out to nauty's ``labelg`` / ``shortg``
for canonical labelling and duplicate removal.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Iterable, List, Sequence, Set, Tuple

Edge = Tuple[int, int]


# --------------------------------------------------------------------------- #
# graph6 encoding / decoding (McKay format).                                   #
# --------------------------------------------------------------------------- #
def _encode_n(n: int) -> List[int]:
    if n <= 62:
        return [n + 63]
    raise ValueError("graph6 helper here only supports n <= 62 (n=37 is fine)")


def edges_to_graph6(n: int, edges: Iterable[Edge]) -> str:
    """Encode an undirected graph (given as an edge set on 0..n-1) to graph6."""
    adj = [[0] * n for _ in range(n)]
    for u, v in edges:
        adj[u][v] = adj[v][u] = 1
    # Column-major upper triangle bit vector: for j in 1..n-1, for i in 0..j-1.
    bits: List[int] = []
    for j in range(1, n):
        for i in range(j):
            bits.append(adj[i][j])
    while len(bits) % 6 != 0:
        bits.append(0)
    data = _encode_n(n)
    for k in range(0, len(bits), 6):
        byte = 0
        for b in range(6):
            byte = (byte << 1) | bits[k + b]
        data.append(byte + 63)
    return "".join(chr(c) for c in data)


def matrix_to_graph6(matrix: Sequence[Sequence[int]]) -> str:
    n = len(matrix)
    edges = [(i, j) for i in range(n) for j in range(i + 1, n) if matrix[i][j]]
    return edges_to_graph6(n, edges)


def graph6_to_matrix(line: str) -> List[List[int]]:
    line = line.strip()
    data = [ord(c) - 63 for c in line]
    n = data[0]
    bits: List[int] = []
    for byte in data[1:]:
        for b in range(5, -1, -1):
            bits.append((byte >> b) & 1)
    matrix = [[0] * n for _ in range(n)]
    idx = 0
    for j in range(1, n):
        for i in range(j):
            if bits[idx]:
                matrix[i][j] = matrix[j][i] = 1
            idx += 1
    return matrix


# --------------------------------------------------------------------------- #
# nauty wrappers.                                                              #
# --------------------------------------------------------------------------- #
def _tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise FileNotFoundError(
            f"nauty tool '{name}' not found on PATH (install nauty, e.g. "
            "'brew install nauty')."
        )
    return path


def canonical_form(g6: str) -> str:
    """Return the nauty canonical graph6 string for a single graph6 input."""
    proc = subprocess.run(
        [_tool("labelg"), "-g"],
        input=g6 + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def canonical_forms(lines: Iterable[str]) -> List[str]:
    """Batch canonical labelling: one ``labelg`` call for many graph6 inputs.

    labelg emits exactly one canonical graph6 line per input line, in order, so
    the result is aligned with the input.  Isomorphic inputs map to identical
    output strings (so ``set(...)`` gives the distinct-graph count).
    """
    items = [ln.strip() for ln in lines if ln.strip()]
    if not items:
        return []
    proc = subprocess.run(
        [_tool("labelg"), "-g"],
        input="\n".join(items) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    out = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if len(out) != len(items):
        raise RuntimeError(
            f"labelg returned {len(out)} lines for {len(items)} inputs")
    return out


def dedup_graph6(lines: Iterable[str]) -> List[str]:
    """Remove isomorphic duplicates from an iterable of graph6 strings.

    Uses nauty's ``shortg`` if available (fast, C implementation); otherwise
    falls back to canonicalising each graph with ``labelg`` and de-duplicating
    the strings in Python.
    """
    items = [ln.strip() for ln in lines if ln.strip()]
    if not items:
        return []
    if shutil.which("shortg"):
        proc = subprocess.run(
            [_tool("shortg"), "-g"],
            input="\n".join(items) + "\n",
            capture_output=True,
            text=True,
            check=True,
        )
        return [ln for ln in proc.stdout.splitlines() if ln.strip()]
    # Fallback: canonicalise individually.
    seen: Set[str] = set()
    out: List[str] = []
    for g6 in items:
        c = canonical_form(g6)
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def dedup_matrices(matrices: Iterable[Sequence[Sequence[int]]]) -> List[List[List[int]]]:
    """Isomorph-reject a collection of adjacency matrices; return survivors."""
    g6s = [matrix_to_graph6(m) for m in matrices]
    canon = dedup_graph6(g6s)
    return [graph6_to_matrix(c) for c in canon]


def nauty_available() -> bool:
    return shutil.which("labelg") is not None or shutil.which("shortg") is not None
