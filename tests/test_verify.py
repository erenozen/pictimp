"""Tests for pairwise verification logic."""
from pairwise_cli.model import PairwiseModel
from pairwise_cli.verify import verify_pairwise_coverage

def test_verify_success():
    model = PairwiseModel()
    model.add_parameter("A", ["A1", "A2"])
    model.add_parameter("B", ["B1", "B2"])
    model.add_parameter("C", ["C1", "C2"])
    
    # an orthogonal array of strength 2 for 2^3
    rows = [
        ["A1", "B1", "C1"],
        ["A1", "B2", "C2"],
        ["A2", "B1", "C2"],
        ["A2", "B2", "C1"]
    ]
    
    passed, missing = verify_pairwise_coverage(model, rows)
    assert passed is True
    assert len(missing) == 0

def test_verify_fail():
    model = PairwiseModel()
    model.add_parameter("A", ["A1", "A2"])
    model.add_parameter("B", ["B1", "B2"])
    
    rows = [
        ["A1", "B1"],
        ["A2", "B1"]
    ]
    
    passed, missing = verify_pairwise_coverage(model, rows)
    assert passed is False
    assert len(missing) == 2
    assert "(A: A1, B: B2)" in missing
    assert "(A: A2, B: B2)" in missing
