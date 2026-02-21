"""Acceptance tests for generator determinism."""
import pytest
import sys
from pathlib import Path

# Add project root to path so we can import expectations
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from acceptance.expectations import run_cli_cmd, assert_successful_exit, parse_json_output
from acceptance.run_acceptance import get_executable_path

CMD_SOURCE = [sys.executable, "-m", "pairwise_cli"]
MODEL_PATH = Path(__file__).parent.parent.parent / "examples" / "sample.pict"

@pytest.fixture(params=["source", "exe"])
def cmd_target(request):
    if request.param == "source":
        return CMD_SOURCE
    else:
        exe_path = get_executable_path()
        if not exe_path:
            pytest.skip("Executable not built")
        return exe_path

@pytest.mark.acceptance
def test_acceptance_determinism(cmd_target):
    args = [
        "generate", "--model", str(MODEL_PATH), "--ordering", "auto", 
        "--strength", "2", "--tries", "40", "--seed", "123", 
        "--deterministic", "--format", "json"
    ]
    rc1, stdout1, stderr1 = run_cli_cmd(cmd_target, args, timeout=15)
    assert_successful_exit(rc1, stderr1)
    
    rc2, stdout2, stderr2 = run_cli_cmd(cmd_target, args, timeout=15)
    assert_successful_exit(rc2, stderr2)
    
    data1 = parse_json_output(stdout1)
    data2 = parse_json_output(stdout2)
    
    assert data1["metadata"] == data2["metadata"], "Metadata mismatch across deterministic runs"
    assert data1["test_cases"] == data2["test_cases"], "Generated cases mismatch across deterministic runs"
