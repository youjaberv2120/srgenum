"""Tests for SRG parameter algebra checks."""

import pytest

from properties import validate_srg_parameters
from srg_encoder import make_spec


@pytest.mark.parametrize(
    "v,k,lam,mu",
    [
        (5, 2, 0, 1),
        (9, 4, 1, 2),
        (10, 3, 0, 1),
        (16, 6, 2, 2),
        (25, 12, 5, 6),
        (26, 10, 3, 4),
        (29, 14, 6, 7),
        (37, 18, 8, 9),
    ],
)
def test_known_parameters_pass(v, k, lam, mu):
    validate_srg_parameters(v, k, lam, mu)
    spec = make_spec(v, k, lam, mu)
    assert spec == (v, k, lam, mu)


@pytest.mark.parametrize(
    "v,k,lam,mu",
    [
        (29, 14, 6, 8),   # mu typo
        (29, 13, 6, 7),   # k typo
        (29, 14, 7, 7),   # lam typo
        (37, 18, 8, 10),  # mu typo on (37)
    ],
)
def test_common_typos_fail(v, k, lam, mu):
    with pytest.raises(ValueError, match="SRG parameter checks failed"):
        validate_srg_parameters(v, k, lam, mu)


def test_impossible_degree_fails():
    with pytest.raises(ValueError, match="k < v"):
        validate_srg_parameters(10, 10, 0, 1)
