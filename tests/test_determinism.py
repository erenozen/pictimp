"""Tests for generator determinism and tie-breaking."""
import pytest
from unittest.mock import patch
from pairwise_cli.model import PairwiseModel
from pairwise_cli.generate import generate_suite, OrderingMode, GenerationResult

def build_dummy_model():
    m = PairwiseModel()
    m.add_parameter("A", ["a1", "a2"])
    m.add_parameter("B", ["b1", "b2"])
    return m

def test_determinism_tie_breaking():
    model = build_dummy_model()
    
    # We will mock run_pict and verify_pairwise_coverage to return
    # arbitrary N sizes to force tie breaking scenarios.
    
    # Let's say seed 0 gives N=5
    # seed 1 gives N=4
    # seed 2 gives N=4
    # seed 3 gives N=3 (verified False)
    
    def mock_run_pict(*args, **kwargs):
        seed = kwargs.get('seed')
        return f"mock_out_seed_{seed}"
        
    def mock_parse_tsv(content, display_map, canonical_headers):
        # Determine rows based on content string
        seed = int(content.split('_')[-1])
        if seed == 0:
            rows = [["x", "y"] for _ in range(5)]
        elif seed in (1, 2):
            rows = [["x", "y"] for _ in range(4)]
        else:
            rows = [["x", "y"] for _ in range(3)]
        return canonical_headers, rows
        
    def mock_verify(model, rows):
        # Assume 3 rows fail, others pass
        if len(rows) == 3:
            return False, ["(A: a1, B: b2)"]
        return True, []
        
    with patch('pairwise_cli.generate.run_pict', side_effect=mock_run_pict):
        with patch('pairwise_cli.generate.PictOutputParser.parse_tsv', side_effect=mock_parse_tsv):
            with patch('pairwise_cli.generate.verify_pairwise_coverage', side_effect=mock_verify):
                
                # Test 1: Standard tie-breaking (keep first seen equal N if deterministic is True)
                res = generate_suite(model, tries=4, deterministic=True, early_stop=False)
                # Seed 1 and 2 give N=4. Seed 3 gives N=3 but fails verify.
                # So we expect N=4. Since deterministic, it should prefer the first one (Seed 1).
                assert res.passed_verification is True
                assert res.n == 4
                assert res.seed == 1
                
                # Test 2: Nondeterministic might prefer later seed depending on OS dict hashing or default behavior.
                # Currently code says: if n == best_n and not deterministic: better = False (so it happens to ALSO be stable!)
                res2 = generate_suite(model, tries=4, deterministic=False, early_stop=False)
                assert res2.n == 4
                assert res2.seed == 1

def test_require_verified_drops_unverified():
    model = build_dummy_model()
    
    def mock_run_pict(*args, **kwargs):
        return "mock"
        
    def mock_parse_tsv(content, display_map, canonical_headers):
        return canonical_headers, [["x", "y"] for _ in range(4)]
        
    def mock_verify(model, rows):
        return False, ["missing"]
        
    with patch('pairwise_cli.generate.run_pict', side_effect=mock_run_pict):
        with patch('pairwise_cli.generate.PictOutputParser.parse_tsv', side_effect=mock_parse_tsv):
            with patch('pairwise_cli.generate.verify_pairwise_coverage', side_effect=mock_verify):
                
                # If require_verified=True, it will throw SystemExit since none pass
                with pytest.raises(SystemExit) as e:
                    generate_suite(model, tries=2, require_verified=True)
                assert e.value.code == 3 # EXIT_PICT_ERR
                
                # If require_verified=False, it should return the best one anyway
                res = generate_suite(model, tries=2, require_verified=False)
                assert res.passed_verification is False
                assert res.n == 4
