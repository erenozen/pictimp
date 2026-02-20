"""Integration tests using the sample.pict model."""
import pytest
import os
from pairwise_cli.pict import get_bundled_pict_path
from pairwise_cli.model import PairwiseModel
from pairwise_cli.generate import generate_suite, OrderingMode

@pytest.fixture
def sample_model_content():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples", "sample.pict")
    if not os.path.exists(path):
        pytest.skip("examples/sample.pict not found")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def test_integration_sample(sample_model_content):
    pict_path = get_bundled_pict_path()
    if not os.path.exists(pict_path):
        pytest.skip(f"Bundled PICT absent for this platform at {pict_path}")
        
    model = PairwiseModel.from_pict_model(sample_model_content)
    
    # Verify using AUTO ordering mode, tries > 1
    res = generate_suite(
        model, 
        ordering_mode=OrderingMode.AUTO, 
        tries=5, 
        base_seed=0, 
        verify=True, 
        verbose=False
    )
    
    assert res.lb == 16
    assert res.passed_verification is True
    assert res.n >= res.lb
    
    if res.n == res.lb:
        print("Note: PICT produced exactly N=16. Provably minimum!")
    else:
        print(f"Note: PICT produced N={res.n}. Lower Bound is {res.lb}.")
