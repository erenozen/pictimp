"""Computes the pairwise lower bound for a given model."""
from typing import List

def compute_pairwise_lower_bound(counts: List[int]) -> int:
    """
    Computes the maximum product of any two parameter value counts.
    LB = max_{i<j} (v_i * v_j).
    If there are less than 2 parameters, returns 0.
    """
    if len(counts) < 2:
        return 0
    
    max_lb = 0
    for i in range(len(counts)):
        for j in range(i + 1, len(counts)):
            product = counts[i] * counts[j]
            if product > max_lb:
                max_lb = product
    return max_lb
