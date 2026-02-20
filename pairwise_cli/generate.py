"""Generation orchestration."""
import sys
from typing import List, Optional, Tuple
from enum import Enum

from .bounds import compute_pairwise_lower_bound
from .pict import run_pict
from .output import PictOutputParser
from .verify import verify_pairwise_coverage
from .model import PairwiseModel

class OrderingMode(str, Enum):
    KEEP = "keep"
    AUTO = "auto"

class GenerationResult:
    def __init__(self, lb: int, n: int, seed: int, rows: List[List[str]],
                 passed_verification: bool, missing_pairs: List[str],
                 canonical_headers: List[str], reordered_params: List['Parameter'],
                 ordering_mode: OrderingMode, attempts: int,
                 internal_pict_model_str: str):
        self.lb = lb
        self.n = n
        self.seed = seed
        self.rows = rows
        self.passed_verification = passed_verification
        self.missing_pairs = missing_pairs
        self.canonical_headers = canonical_headers
        self.reordered_params = reordered_params
        self.ordering_mode = ordering_mode
        self.attempts = attempts
        self.internal_pict_model_str = internal_pict_model_str

def generate_suite(model: PairwiseModel, 
                   ordering_mode: OrderingMode = OrderingMode.AUTO,
                   tries: int = 50,
                   base_seed: int = 0,
                   strength: int = 2,
                   early_stop: bool = True,
                   verify: bool = True,
                   require_verified: bool = True,
                   pict_timeout_sec: float = 10.0,
                   deterministic: bool = False,
                   verbose: bool = False) -> GenerationResult:
    """Runs PICT multiple times and returns the best generated suite."""
    if ordering_mode == OrderingMode.AUTO:
        # Use stable sort built into get_reordered_parameters
        run_params = model.get_reordered_parameters()
    else:
        run_params = model.parameters
        
    pict_model_str = model.to_pict_model(run_params)
    canonical_headers = [p.display_name for p in model.parameters]
    display_map = model.get_safe_to_display_map()
    
    lb = compute_pairwise_lower_bound(model.get_counts()) if strength == 2 else 0
    
    best_n = float('inf')
    best_rows = []
    best_seed = 0
    best_passed = False
    best_missing = []
    
    # Deterministic behavior overrides tries logic slightly if needed
    # (By default base_seed+i loop is deterministic, but we explicitly enforce tie-breaks)
    
    for i in range(tries):
        current_seed = base_seed + i
        try:
            pict_out = run_pict(pict_model_str, strength=strength, seed=current_seed, timeout=pict_timeout_sec)
        except TimeoutError as e:
            if verbose:
                print(f"PICT timeout on try {i+1}: {e}", file=sys.stderr)
            continue
        except Exception as e:
            if verbose:
                print(f"Error running generation on try {i+1}: {e}", file=sys.stderr)
            continue
            
        headers, rows = PictOutputParser.parse_tsv(pict_out, display_map, canonical_headers)
        n = len(rows)
        
        passed = True
        missing = []
        if verify and strength == 2:
            passed, missing = verify_pairwise_coverage(model, rows)
            
        if require_verified and not passed:
            if verbose:
                print(f"  Attempt {i+1}/{tries} (seed {current_seed}): FAILED verification (missing {len(missing)} pairs)")
            continue

        better = False
        if best_n == float('inf'):
            better = True
        elif passed and not best_passed:
            better = True
        elif passed == best_passed:
            # Deterministic tie-breaking:
            if n < best_n:
                better = True
            elif n == best_n:
                if deterministic:
                    # Keep older seed to maintain stable identical selections 
                    better = False
                else:
                    better = False # default to first encountered regardless

        if better:
            best_n = n
            best_rows = rows
            best_seed = current_seed
            best_passed = passed
            best_missing = missing
            
            if verbose:
                flag = " (PROVABLY MINIMUM)" if best_n == lb and strength == 2 else ""
                print(f"  Attempt {i+1}/{tries} (seed {current_seed}): N={n}{flag}")
                
            if early_stop and strength == 2 and best_n == lb and passed:
                if verbose:
                    print(f"  Stopping early at attempt {i+1} because lower bound {lb} was reached and coverage verified.")
                return GenerationResult(
                    lb, best_n, best_seed, best_rows, best_passed, best_missing,
                    canonical_headers, run_params, ordering_mode, i + 1, pict_model_str
                )
                
    if best_n == float('inf'):
        if require_verified:
            err = "All generation attempts failed either to execute or failed coverage verification."
        else:
            err = "All generation attempts failed to execute."
        from . import EXIT_PICT_ERR
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(EXIT_PICT_ERR)
        
    return GenerationResult(
        lb, best_n, best_seed, best_rows, best_passed, best_missing,
        canonical_headers, run_params, ordering_mode, tries, pict_model_str
    )
