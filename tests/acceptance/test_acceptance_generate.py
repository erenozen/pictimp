"""Acceptance tests for generate command."""
import pytest
import sys
from pathlib import Path

# Add project root to path so we can import expectations
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from acceptance.expectations import run_cli_cmd, assert_successful_exit, parse_json_output, assert_generate_json
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
def test_acceptance_generate_auto(cmd_target):
    args = [
        "generate", "--model", str(MODEL_PATH), "--ordering", "auto", 
        "--strength", "2", "--tries", "40", "--seed", "0", 
        "--deterministic", "--format", "json"
    ]
    rc, stdout, stderr = run_cli_cmd(cmd_target, args, timeout=15)
    assert_successful_exit(rc, stderr)
    
    data = parse_json_output(stdout)
    assert_generate_json(data)
    
    meta = data["metadata"]
    assert meta["lb"] == 16, f"Expected LB=16, got {meta['lb']}"
    assert meta["n"] >= 16, f"Expected N>=16, got {meta['n']}"
    assert meta["verified"] is True, "Expected verified=True"

@pytest.mark.acceptance
def test_acceptance_generate_keep(cmd_target):
    args = [
        "generate", "--model", str(MODEL_PATH), "--ordering", "keep", 
        "--strength", "2", "--tries", "40", "--seed", "0", 
        "--deterministic", "--format", "json"
    ]
    rc, stdout, stderr = run_cli_cmd(cmd_target, args, timeout=15)
    assert_successful_exit(rc, stderr)
    
    data = parse_json_output(stdout)
    assert_generate_json(data)
    
    meta = data["metadata"]
    assert meta["lb"] == 16, f"Expected LB=16, got {meta['lb']}"
    assert meta["n"] >= 16, f"Expected N>=16, got {meta['n']}"
    assert meta["verified"] is True, "Expected verified=True"
