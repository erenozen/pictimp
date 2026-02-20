"""Pairwise coverage verification logic."""
from typing import List, Tuple
from .model import PairwiseModel

def verify_pairwise_coverage(model: PairwiseModel, rows: List[List[str]]) -> Tuple[bool, List[str]]:
    """
    Verifies that all possible pairs of parameter values are covered in the generated test suite.
    Assumes `rows` are ordered according to the canonical parameters in the model.
    """
    num_params = len(model.parameters)
    if num_params < 2:
        return True, []
        
    value_maps = []
    for p in model.parameters:
        vmap = {v: idx for idx, v in enumerate(p.values)}
        value_maps.append(vmap)
        
    # covered_pairs[(p1_idx, p2_idx)] = set of (v1_idx, v2_idx)
    covered_pairs = {}
    for i in range(num_params):
        for j in range(i + 1, num_params):
            covered_pairs[(i, j)] = set()
            
    for row_idx, row in enumerate(rows):
        if len(row) < num_params:
            continue
            
        row_v_indices = []
        for i in range(num_params):
            val = row[i]
            if val not in value_maps[i]:
                raise ValueError(f"CRITICAL: Generated value '{val}' at row {row_idx+1}, col {i+1} is not a valid parameter value in the model for '{model.parameters[i].display_name}'.")
            row_v_indices.append(value_maps[i][val])
            
        for i in range(num_params):
            for j in range(i + 1, num_params):
                covered_pairs[(i, j)].add((row_v_indices[i], row_v_indices[j]))
                
    missing_pairs = []
    
    for i in range(num_params):
        for j in range(i + 1, num_params):
            p1 = model.parameters[i]
            p2 = model.parameters[j]
            
            p1_count = len(p1.values)
            p2_count = len(p2.values)
            
            if len(covered_pairs[(i, j)]) == p1_count * p2_count:
                continue
                
            for v1_idx in range(p1_count):
                for v2_idx in range(p2_count):
                    if (v1_idx, v2_idx) not in covered_pairs[(i, j)]:
                        missing_pairs.append(f"({p1.display_name}: {p1.values[v1_idx]}, {p2.display_name}: {p2.values[v2_idx]})")
                        if len(missing_pairs) >= 20:
                            return False, missing_pairs
                            
    return len(missing_pairs) == 0, missing_pairs
