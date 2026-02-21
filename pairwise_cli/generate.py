"""Generation orchestration."""
import sys
import time
from typing import List, Optional
from enum import Enum

from .bounds import compute_pairwise_lower_bound
from .pict import run_pict
from .output import PictOutputParser
from .verify import verify_pairwise_coverage
from .model import PairwiseModel

class OrderingMode(str, Enum):
    KEEP = "keep"
    AUTO = "auto"

class GenerationVerificationError(Exception):
    """Raised when verified output is required but no verified suite is found."""
    def __init__(self, message: str, missing_pairs: Optional[List[str]] = None):
        super().__init__(message)
        self.missing_pairs = missing_pairs or []

class GenerationExecutionError(Exception):
    """Raised when generation fails for non-timeout, non-verification reasons."""

class GenerationResult:
    def __init__(self, lb: Optional[int], n: int, seed: int, rows: List[List[str]],
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
                   total_timeout_sec: float = 30.0,
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
    
    lb = compute_pairwise_lower_bound(model.get_counts()) if strength == 2 else None
    verification_enabled = verify and strength >= 2
    
    best_n = float('inf')
    best_rows = []
    best_seed = base_seed
    best_passed = False
    best_missing = []
    attempts_done = 0
    timeout_attempts = 0
    had_non_timeout_error = False
    deadline = time.monotonic() + total_timeout_sec

    best_failing_missing = None
    best_failing_seed = None
    
    for i in range(tries):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Total generation timeout exceeded before all attempts completed.")

        current_seed = base_seed + i
        attempts_done = i + 1
        attempt_timeout = min(pict_timeout_sec, remaining)
        try:
            pict_out = run_pict(
                pict_model_str,
                strength=strength,
                seed=current_seed,
                timeout=attempt_timeout
            )
        except TimeoutError as e:
            timeout_attempts += 1
            if verbose:
                print(f"PICT timeout on try {i+1}: {e}", file=sys.stderr)
            continue
        except Exception as e:
            had_non_timeout_error = True
            if verbose:
                print(f"Error running generation on try {i+1}: {e}", file=sys.stderr)
            continue
            
        try:
            _, rows = PictOutputParser.parse_tsv(pict_out, display_map, canonical_headers)
        except Exception as e:
            had_non_timeout_error = True
            if verbose:
                print(f"Error parsing PICT output on try {i+1}: {e}", file=sys.stderr)
            continue
        n = len(rows)
        
        passed = False
        missing = []
        if verification_enabled:
            passed, missing = verify_pairwise_coverage(model, rows)
            
        if verification_enabled and require_verified and not passed:
            if (
                best_failing_missing is None
                or len(missing) < len(best_failing_missing)
                or (len(missing) == len(best_failing_missing) and (best_failing_seed is None or current_seed < best_failing_seed))
            ):
                best_failing_missing = list(missing)
                best_failing_seed = current_seed
            if verbose:
                print(
                    f"Attempt {i+1}/{tries} (seed {current_seed}): FAILED verification (missing {len(missing)} pairs)",
                    file=sys.stderr
                )
            continue

        better = False
        if best_n == float('inf'):
            better = True
        elif n < best_n:
            better = True
        elif n == best_n and current_seed < best_seed:
            better = True

        if better:
            best_n = n
            best_rows = rows
            best_seed = current_seed
            best_passed = passed
            best_missing = missing
            
            if verbose:
                flag = ""
                if strength == 2 and passed and lb is not None and best_n == lb:
                    flag = " (PROVABLY MINIMUM)"
                print(f"Attempt {i+1}/{tries} (seed {current_seed}): N={n}{flag}", file=sys.stderr)
                
            if early_stop and strength == 2 and passed and lb is not None and best_n == lb:
                if verbose:
                    print(
                        f"Stopping early at attempt {i+1} because lower bound {lb} was reached and coverage verified.",
                        file=sys.stderr
                    )
                return GenerationResult(
                    lb, best_n, best_seed, best_rows, best_passed, best_missing,
                    canonical_headers, run_params, ordering_mode, i + 1, pict_model_str
                )
                
    if best_n == float('inf'):
        if timeout_attempts == tries:
            raise TimeoutError("All generation attempts timed out.")
        if verification_enabled and require_verified and best_failing_missing is not None:
            raise GenerationVerificationError(
                "All generation attempts failed coverage verification.",
                missing_pairs=best_failing_missing
            )
        if had_non_timeout_error:
            raise GenerationExecutionError("All generation attempts failed to execute.")
        if timeout_attempts > 0:
            raise TimeoutError("Generation timed out before any valid suite could be produced.")
        raise GenerationExecutionError("All generation attempts failed.")
        
    return GenerationResult(
        lb, best_n, best_seed, best_rows, best_passed, best_missing,
        canonical_headers, run_params, ordering_mode, attempts_done, pict_model_str
    )
