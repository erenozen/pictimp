"""Pairwise coverage verification logic."""
from typing import List, Tuple
from .model import PairwiseModel

def verify_pairwise_coverage(model: PairwiseModel, rows: List[List[str]]) -> Tuple[bool, List[str]]:
    """
    Verifies that all possible pairs of parameter values are covered in the generated test suite.
    Assumes `rows` are ordered according to the canonical parameters in the model.
    """
    if len(model.parameters) < 2:
        return True, []
        
    missing_pairs = []
    
    for i in range(len(model.parameters)):
        for j in range(i + 1, len(model.parameters)):
            p1 = model.parameters[i]
            p2 = model.parameters[j]
            
            for v1 in p1.values:
                for v2 in p2.values:
                    # Check if the pair (v1, v2) appears in any row at the corresponding columns (i, j)
                    found = False
                    for row in rows:
                        if len(row) > max(i, j):
                            if row[i] == v1 and row[j] == v2:
                                found = True
                                break
                    if not found:
                        missing_pairs.append(f"({p1.display_name}: {v1}, {p2.display_name}: {v2})")
                        if len(missing_pairs) >= 20:
                            return False, missing_pairs
                            
    return len(missing_pairs) == 0, missing_pairs
