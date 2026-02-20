"""Tests for the interactive wizard using mock inputs."""
import pytest
from unittest.mock import patch
from pairwise_cli.wizard import _gather_parameters, _generate_and_present
from pairwise_cli.model import PairwiseModel

def test_wizard_gather_parameters():
    model = PairwiseModel()
    
    # We will mock the user input sequence:
    # 1. Enter param 'A'
    # 2. Enter values '1, 2'
    # 3. Enter param 'B'
    # 4. Enter values '3, 4'
    # 5. Enter blank param (to finish)
    
    inputs = [
        "A",
        "1, 2",
        "B",
        "3, 4",
        ""
    ]
    
    def mock_prompt(msg):
        return inputs.pop(0)
        
    with patch('pairwise_cli.wizard.prompt', side_effect=mock_prompt):
        _gather_parameters(model)
        
    assert len(model.parameters) == 2
    assert model.parameters[0].display_name == "A"
    assert model.parameters[0].values == ["1", "2"]
    assert model.parameters[1].display_name == "B"
    assert model.parameters[1].values == ["3", "4"]

def test_wizard_gather_parameters_invalid_retries():
    model = PairwiseModel()
    
    # Sequence:
    # 1. Enter param 'A'
    # 2. Enter values '1' (invalid, needs >= 2) - Should catch ValueError and retry
    # 3. Enter param 'A'
    # 4. Enter values '1, 2'
    # 5. Enter param 'B'
    # 6. Enter values '3, 4'
    # 7. Enter blank
    
    inputs = [
        "A",
        "1",
        "A",
        "1, 2",
        "B",
        "3, 4",
        ""
    ]
    
    def mock_prompt(msg):
        return inputs.pop(0)
        
    with patch('pairwise_cli.wizard.prompt', side_effect=mock_prompt):
        _gather_parameters(model)
        
    assert len(model.parameters) == 2
    assert model.parameters[0].values == ["1", "2"]

def test_wizard_generate_and_present_flow():
    model = PairwiseModel()
    model.add_parameter("A", ["1", "2"])
    model.add_parameter("B", ["3", "4"])
    
    # Sequence for _generate_and_present:
    # 1. Ordering: '2' (Auto)
    # 2. Tries: '5'
    # 3. Verify: 'y'
    # 4. Save: 'n'
    
    inputs = ["2", "5", "y", "n"]
    
    def mock_prompt(msg):
        return inputs.pop(0)
        
    class MockRes:
        passed_verification = True
        canonical_headers = ["A", "B"]
        rows = [["1", "3"], ["1", "4"], ["2", "3"], ["2", "4"]]
        ordering_mode = "auto"
        reordered_params = model.parameters
        attempts = 5
        seed = 123
        lb = 4
        n = 4
        internal_pict_model_str = "mock"
        
    with patch('pairwise_cli.wizard.prompt', side_effect=mock_prompt):
        with patch('pairwise_cli.wizard.generate_suite', return_value=MockRes()):
            with patch('builtins.print'):
                with pytest.raises(SystemExit) as e:
                    _generate_and_present(model)
                assert e.value.code == 0
