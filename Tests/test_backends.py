"""Backend-agreement tests: PySAT and smsg must produce the same canonical set."""

import pytest

from srg_encoder import CNFBuilder, add_srg_constraints, SRGSpec
import sat_backend
import iso


SMALL = [
    (5, 2, 0, 1, 1),    # C5
    (9, 4, 1, 2, 1),    # Paley(9)
    (10, 3, 0, 1, 1),   # Petersen
]


def _canonical_set_pysat(spec):
    b = CNFBuilder(spec.V)
    add_srg_constraints(b, spec)
    mats = sat_backend.enumerate_pysat(b, spec.V)
    return set(iso.dedup_graph6([iso.matrix_to_graph6(m) for m in mats]))


def _canonical_set_smsg(spec, out_dir="Output"):
    import os
    os.makedirs(out_dir, exist_ok=True)
    b = CNFBuilder(spec.V)
    meta = add_srg_constraints(b, spec)
    path = os.path.join(out_dir, f"_test_{spec.V}_{spec.degree}.cnf")
    b.to_dimacs(path)
    try:
        mats = sat_backend.enumerate_smsg(
            path, spec.V, initial_partition=meta["initial_partition"], timeout=60)
    finally:
        if os.path.exists(path):
            os.remove(path)
    return set(iso.dedup_graph6([iso.matrix_to_graph6(m) for m in mats]))


@pytest.mark.parametrize("v,k,lam,mu,expected", SMALL)
def test_pysat_counts(v, k, lam, mu, expected):
    canon = _canonical_set_pysat(SRGSpec(v, k, lam, mu))
    assert len(canon) == expected


@pytest.mark.skipif(not sat_backend.has_smsg(), reason="smsg not built")
@pytest.mark.parametrize("v,k,lam,mu,expected", SMALL)
def test_backends_agree(v, k, lam, mu, expected):
    spec = SRGSpec(v, k, lam, mu)
    canon_pysat = _canonical_set_pysat(spec)
    canon_smsg = _canonical_set_smsg(spec)
    assert canon_pysat == canon_smsg
    assert len(canon_smsg) == expected
