"""Tests for the interactive wizard using mock inputs."""
import pytest
from unittest.mock import patch
from pairwise_cli.wizard import (
    _delete_parameter,
    _gather_parameters,
    _generate_and_present,
    _menu_loop,
    run_wizard,
)
from pairwise_cli.model import PairwiseModel
from pairwise_cli.generate import OrderingMode

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
                assert _generate_and_present(model) is True


def test_wizard_no_verify_does_not_claim_minimum():
    model = PairwiseModel()
    model.add_parameter("A", ["1", "2"])
    model.add_parameter("B", ["3", "4"])

    inputs = ["2", "5", "n", "n"]

    def mock_prompt(msg):
        return inputs.pop(0)

    class MockRes:
        passed_verification = False
        canonical_headers = ["A", "B"]
        rows = [["1", "3"], ["2", "4"]]
        ordering_mode = OrderingMode.AUTO
        reordered_params = model.parameters
        attempts = 5
        seed = 123
        lb = 4
        n = 4
        internal_pict_model_str = "mock"

    with patch("pairwise_cli.wizard.prompt", side_effect=mock_prompt):
        with patch("pairwise_cli.wizard.generate_suite", return_value=MockRes()):
            with patch("builtins.print") as mock_print:
                assert _generate_and_present(model) is True

    printed = "\n".join(
        str(call.args[0]) for call in mock_print.call_args_list if call.args
    )
    assert "PROVABLY MINIMUM" not in printed
    assert "Result: COVERAGE NOT VERIFIED" in printed


def test_wizard_save_outputs_txt_files(tmp_path, monkeypatch):
    model = PairwiseModel()
    model.add_parameter("A", ["1", "2"])
    model.add_parameter("B", ["3", "4"])

    inputs = ["2", "5", "y", "y"]

    def mock_prompt(msg):
        return inputs.pop(0)

    class MockRes:
        passed_verification = True
        canonical_headers = ["A", "B"]
        rows = [["1", "3"], ["1", "4"], ["2", "3"], ["2", "4"]]
        ordering_mode = OrderingMode.AUTO
        reordered_params = model.parameters
        attempts = 5
        seed = 123
        lb = 4
        n = 4
        internal_pict_model_str = "A: 1, 2\nB: 3, 4\n"

    with patch("pairwise_cli.wizard.prompt", side_effect=mock_prompt):
        with patch("pairwise_cli.wizard.generate_suite", return_value=MockRes()):
            with patch("builtins.print"):
                monkeypatch.chdir(tmp_path)
                assert _generate_and_present(model) is True

    assert (tmp_path / "pairwise_model.txt").exists()
    assert (tmp_path / "pairwise_cases.txt").exists()
    assert (tmp_path / "pairwise_model.reordered.txt").exists()


def test_run_wizard_repeat_flow_then_exit():
    def populate_model(model):
        model.add_parameter("A", ["1", "2"])
        model.add_parameter("B", ["3", "4"])

    with patch("pairwise_cli.wizard._gather_parameters", side_effect=populate_model) as gather_mock:
        with patch("pairwise_cli.wizard._menu_loop", side_effect=["generated", "generated"]) as menu_mock:
            with patch("pairwise_cli.wizard.prompt", side_effect=["y", "n"]):
                with patch("builtins.print"):
                    run_wizard()

    assert gather_mock.call_count == 2
    assert menu_mock.call_count == 2


def test_wizard_generate_requires_min_two_parameters():
    model = PairwiseModel()

    with patch("pairwise_cli.wizard.generate_suite") as gen_mock:
        with patch("builtins.print") as print_mock:
            assert _generate_and_present(model) is False

    gen_mock.assert_not_called()
    printed = "\n".join(
        str(call.args[0]) for call in print_mock.call_args_list if call.args
    )
    assert "Input Error:" in printed
    assert "At least 2 parameters are required." in printed


def test_menu_loop_does_not_transition_to_generated_when_generation_fails():
    model = PairwiseModel()
    model.add_parameter("A", ["1", "2"])
    model.add_parameter("B", ["3", "4"])

    with patch("pairwise_cli.wizard.prompt", side_effect=["1", "1"]):
        with patch("pairwise_cli.wizard._generate_and_present", side_effect=[False, True]) as gen_mock:
            action = _menu_loop(model)

    assert action == "generated"
    assert gen_mock.call_count == 2


def test_delete_all_then_generate_does_not_crash_and_returns_to_menu():
    model = PairwiseModel()
    model.add_parameter("A", ["1", "2"])
    model.add_parameter("B", ["3", "4"])

    # delete #1, delete #1, generate (invalid), then quit
    inputs = ["3", "1", "3", "1", "1", "5"]
    with patch("pairwise_cli.wizard.prompt", side_effect=inputs):
        with patch("builtins.print") as print_mock:
            action = _menu_loop(model)

    assert action == "quit"
    assert len(model.parameters) == 0
    printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list if call.args)
    assert "Input Error:" in printed
    assert "At least 2 parameters are required." in printed


def test_invalid_menu_choice_spam_no_crash():
    model = PairwiseModel()
    model.add_parameter("A", ["1", "2"])
    model.add_parameter("B", ["3", "4"])

    with patch("pairwise_cli.wizard.prompt", side_effect=["bad", "", "@", "5"]):
        with patch("builtins.print"):
            action = _menu_loop(model)
    assert action == "quit"


def test_invalid_delete_index_cases_no_crash_and_no_mutation():
    model = PairwiseModel()
    model.add_parameter("A", ["1", "2"])
    model.add_parameter("B", ["3", "4"])

    for bad_input in ["abc", "0", "-1", "3"]:
        with patch("pairwise_cli.wizard.prompt", return_value=bad_input):
            with patch("builtins.print"):
                _delete_parameter(model)

    assert len(model.parameters) == 2


def test_wizard_duplicate_parameter_name_attempt_recovers():
    model = PairwiseModel()
    inputs = ["A", "1,2", "a", "3,4", "B", "3,4", ""]

    with patch("pairwise_cli.wizard.prompt", side_effect=inputs):
        with patch("builtins.print"):
            _gather_parameters(model)

    assert len(model.parameters) == 2
    assert model.parameters[0].display_name == "A"
    assert model.parameters[1].display_name == "B"


def test_wizard_duplicate_value_attempt_recovers():
    model = PairwiseModel()
    inputs = ["A", "1,1", "A", "1,2", "B", "3,4", ""]

    with patch("pairwise_cli.wizard.prompt", side_effect=inputs):
        with patch("builtins.print"):
            _gather_parameters(model)

    assert len(model.parameters) == 2
    assert model.parameters[0].values == ["1", "2"]


def test_wizard_whitespace_parameter_name_recovers():
    model = PairwiseModel()
    inputs = ["   ", "A", "1,2", "B", "3,4", ""]

    with patch("builtins.input", side_effect=inputs):
        with patch("builtins.print"):
            _gather_parameters(model)

    assert len(model.parameters) == 2


def test_wizard_empty_values_list_recovers():
    model = PairwiseModel()
    inputs = ["A", "", "", "A", "1,2", "B", "3,4", ""]

    with patch("pairwise_cli.wizard.prompt", side_effect=inputs):
        with patch("builtins.print"):
            _gather_parameters(model)

    assert len(model.parameters) == 2


def test_wizard_eof_graceful_cancel_no_traceback():
    with patch("builtins.input", side_effect=EOFError):
        with patch("builtins.print") as print_mock:
            run_wizard()

    printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list if call.args)
    assert "Input cancelled (EOF)." in printed
    assert "Traceback (most recent call last)" not in printed


def test_wizard_ctrl_c_graceful_cancel_no_traceback():
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        with patch("builtins.print") as print_mock:
            run_wizard()

    printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list if call.args)
    assert "Cancelled by user." in printed
    assert "Traceback (most recent call last)" not in printed


def test_wizard_save_error_recovers_without_crash():
    model = PairwiseModel()
    model.add_parameter("A", ["1", "2"])
    model.add_parameter("B", ["3", "4"])

    inputs = ["2", "5", "y", "y"]

    def mock_prompt(msg):
        return inputs.pop(0)

    class MockRes:
        passed_verification = True
        canonical_headers = ["A", "B"]
        rows = [["1", "3"], ["2", "4"]]
        ordering_mode = OrderingMode.AUTO
        reordered_params = model.parameters
        attempts = 5
        seed = 123
        lb = 4
        n = 4
        internal_pict_model_str = "A: 1, 2\nB: 3, 4\n"

    with patch("pairwise_cli.wizard.prompt", side_effect=mock_prompt):
        with patch("pairwise_cli.wizard.generate_suite", return_value=MockRes()):
            with patch("builtins.open", side_effect=OSError("read-only")):
                with patch("builtins.print") as print_mock:
                    assert _generate_and_present(model) is False

    printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list if call.args)
    assert "Save Error:" in printed
