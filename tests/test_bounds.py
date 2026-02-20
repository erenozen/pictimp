"""Tests for lower bound computation."""
from pairwise_cli.bounds import compute_pairwise_lower_bound

def test_lower_bound_empty():
    assert compute_pairwise_lower_bound([]) == 0

def test_lower_bound_single():
    assert compute_pairwise_lower_bound([5]) == 0

def test_lower_bound_two_params():
    assert compute_pairwise_lower_bound([3, 4]) == 12

def test_lower_bound_multiple():
    # Example from problem statement: counts = 4, 4, 3, 3, 3 -> max pair is 4 * 4 = 16
    assert compute_pairwise_lower_bound([4, 4, 3, 3, 3]) == 16
    assert compute_pairwise_lower_bound([2, 5, 2, 8]) == 40
