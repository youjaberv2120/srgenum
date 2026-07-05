"""SAT back-ends for ALL-SAT enumeration of SRG models.

Two engines are supported:

* **PySAT + CaDiCaL** (default, always available): in-process solving with
  blocking-clause ALL-SAT *projected onto the edge variables* so that models
  differing only in auxiliary (counter / common-neighbour) variables are not
  double-counted.  Isomorphic duplicates are removed afterwards by nauty.

* **smsg (SAT Modulo Symmetries)** (preferred when built): isomorph-free
  enumeration with dynamic symmetry breaking, invoked on the shared DIMACS
  file.  Used automatically when the ``smsg`` binary is on PATH.

Both consume the SMS-compatible edge-variable layout produced by
:mod:`srg_encoder`, so the same encoding drives either engine.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from itertools import combinations
from typing import List, Optional, Sequence

from srg_encoder import CNFBuilder


# --------------------------------------------------------------------------- #
# helpers                                                                       #
# --------------------------------------------------------------------------- #
def _edge_pairs(n: int):
    """Edge index -> (u, v), matching CNFBuilder's combinations(range(n),2)."""
    return list(combinations(range(n), 2))


def model_to_matrix(n: int, positive: set, builder: CNFBuilder) -> List[List[int]]:
    matrix = [[0] * n for _ in range(n)]
    for u, v in combinations(range(n), 2):
        if builder.var_edge(u, v) in positive:
            matrix[u][v] = matrix[v][u] = 1
    return matrix


# --------------------------------------------------------------------------- #
# PySAT / CaDiCaL engine                                                        #
# --------------------------------------------------------------------------- #
def _pick_pysat_solver():
    from pysat.solvers import Solver

    last_err = None
    for name in ("cadical195", "cadical153", "cadical", "glucose42", "glucose4",
                 "minisat22"):
        try:
            return Solver(name=name), name
        except Exception as exc:  # solver not compiled into this build
            last_err = exc
            continue
    raise RuntimeError(f"No usable PySAT solver backend found ({last_err}).")


def enumerate_projected(
    clauses,
    proj_vars: Sequence[int],
    *,
    limit: Optional[int] = None,
) -> List[frozenset]:
    """Projected ALL-SAT: enumerate all distinct truth-assignments to
    ``proj_vars`` extendable to a model of ``clauses``.

    Returns a list of frozensets, each the set of ``proj_vars`` that are true.
    Blocking clauses are added over ``proj_vars`` only, so models differing only
    in auxiliary variables are not double-counted.
    """
    solver, _name = _pick_pysat_solver()
    proj = list(proj_vars)
    try:
        for cl in clauses:
            solver.add_clause(cl)
        out: List[frozenset] = []
        while solver.solve():
            mset = set(solver.get_model())
            positive = frozenset(v for v in proj if v in mset)
            out.append(positive)
            solver.add_clause([-v if v in positive else v for v in proj])
            if limit is not None and len(out) >= limit:
                break
        return out
    finally:
        solver.delete()


def enumerate_pysat(
    builder: CNFBuilder,
    n: int,
    *,
    limit: Optional[int] = None,
) -> List[List[List[int]]]:
    """Enumerate all edge-assignments satisfying the formula (projected ALL-SAT).

    Returns a list of adjacency matrices (with isomorphic duplicates still
    present; run them through :mod:`iso` to reject).
    """
    edge_vars = [builder.var_edge(u, v) for u, v in combinations(range(n), 2)]
    results: List[List[List[int]]] = []
    for positive in enumerate_projected(builder.clauses, edge_vars, limit=limit):
        results.append(model_to_matrix(n, set(positive), builder))
    return results


# --------------------------------------------------------------------------- #
# smsg engine                                                                   #
# --------------------------------------------------------------------------- #
def smsg_path() -> Optional[str]:
    p = shutil.which("smsg")
    if p:
        return p
    cand = os.path.expanduser("~/.local/bin/smsg")
    return cand if os.path.exists(cand) else None


_EDGE_LINE = re.compile(r"^\s*\[")
_NGRAPHS_LINE = re.compile(r"Number of graphs:\s*(\d+)")
_END_LINE = re.compile(r"Total time:")


def _parse_graph_line(line: str, n: int):
    try:
        edges = eval(line, {"__builtins__": {}})
    except Exception:
        return None
    matrix = [[0] * n for _ in range(n)]
    for e in edges:
        u, v = int(e[0]), int(e[1])
        matrix[u][v] = matrix[v][u] = 1
    return matrix


def run_smsg(
    dimacs_path: str,
    n: int,
    *,
    initial_partition: Optional[str] = None,
    all_graphs: bool = True,
    frequency: int = 20,
    cutoff: int = 20000,
    limit: Optional[int] = None,
    timeout: Optional[float] = None,
    cube_file: Optional[str] = None,
    cube_line: Optional[int] = None,
    cubes_range: Optional[str] = None,
    cube_timeout: Optional[float] = None,
    collect: bool = True,
    extra_args: Optional[Sequence[str]] = None,
) -> dict:
    """Run ``smsg`` (optionally on a single cube) and stream-parse the output.

    Returns a dict with:
      * ``matrices``   -- list of adjacency matrices (empty if ``collect`` False)
      * ``n_graphs``   -- smsg's own "Number of graphs" count if it terminated
      * ``completed``  -- True iff smsg finished the search (not killed by timeout)
      * ``timed_out``  -- True iff the watchdog terminated it
    """
    exe = smsg_path()
    if exe is None:
        raise FileNotFoundError("smsg binary not found (build SMS first).")

    cmd = [exe, "-v", str(n), "--dimacs", dimacs_path,
           "--frequency", str(frequency), "--cutoff", str(cutoff)]
    if all_graphs:
        cmd.append("--all-graphs")
    if initial_partition:
        cmd += ["--initial-partition", initial_partition]
    if cube_file:
        cmd += ["--cube-file", cube_file]
        if cube_line is not None:
            cmd += ["--cube-line", str(cube_line)]
        if cubes_range is not None:
            cmd += ["--cubes-range", cubes_range]
        if cube_timeout is not None:
            cmd += ["--cube-timeout", str(int(cube_timeout))]
    if extra_args:
        cmd += list(extra_args)

    import threading

    matrices: List[List[List[int]]] = []
    n_graphs = None
    saw_end = False
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True)

    timed_out = {"flag": False}

    def _kill():
        timed_out["flag"] = True
        proc.terminate()

    watchdog = None
    if timeout is not None:
        watchdog = threading.Timer(timeout, _kill)
        watchdog.daemon = True
        watchdog.start()

    try:
        for line in proc.stdout:
            if _EDGE_LINE.match(line):
                if collect:
                    m = _parse_graph_line(line, n)
                    if m is not None:
                        matrices.append(m)
                        if limit is not None and len(matrices) >= limit:
                            break
                continue
            mo = _NGRAPHS_LINE.search(line)
            if mo:
                n_graphs = int(mo.group(1))
            elif _END_LINE.search(line):
                saw_end = True
    finally:
        if watchdog is not None:
            watchdog.cancel()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    # A run is "completed" only if smsg reached its natural end (printed the
    # "Total time:" summary) and the watchdog did not kill it.  A cube that is
    # abandoned mid-search (watchdog, or smsg's own --cube-timeout) does NOT
    # print that line, so it is correctly reported as incomplete.
    reached_limit = limit is not None and len(matrices) >= limit
    return {
        "matrices": matrices,
        "n_graphs": n_graphs,
        "completed": (saw_end or reached_limit) and not timed_out["flag"],
        "timed_out": timed_out["flag"],
    }


def enumerate_smsg(
    dimacs_path: str,
    n: int,
    *,
    initial_partition: Optional[str] = None,
    all_graphs: bool = True,
    frequency: int = 20,
    cutoff: int = 20000,
    limit: Optional[int] = None,
    timeout: Optional[float] = None,
    extra_args: Optional[Sequence[str]] = None,
) -> List[List[List[int]]]:
    """Backward-compatible wrapper: return just the list of matrices."""
    res = run_smsg(
        dimacs_path, n, initial_partition=initial_partition,
        all_graphs=all_graphs, frequency=frequency, cutoff=cutoff,
        limit=limit, timeout=timeout, extra_args=extra_args)
    return res["matrices"]


def generate_cubes(
    dimacs_path: str,
    n: int,
    simple_cutoff: int,
    *,
    initial_partition: Optional[str] = None,
    timeout: Optional[float] = None,
) -> List[str]:
    """Generate cube-and-conquer cubes via ``--simple-assignment-cutoff``.

    Returns the list of cube lines (each an ``a <lits> 0`` string) which can be
    written to a file and fed back with ``--cube-file`` / ``--cube-line``.
    """
    exe = smsg_path()
    if exe is None:
        raise FileNotFoundError("smsg binary not found (build SMS first).")
    cmd = [exe, "-v", str(n), "--dimacs", dimacs_path,
           "--simple-assignment-cutoff", str(simple_cutoff)]
    if initial_partition:
        cmd += ["--initial-partition", initial_partition]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return [ln for ln in proc.stdout.splitlines() if ln.startswith("a ")]


def has_smsg() -> bool:
    return smsg_path() is not None
