"""Acceptance tests for doctor command."""
import pytest
import sys
from pathlib import Path

# Add project root to path so we can import expectations
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from acceptance.expectations import run_cli_cmd, assert_successful_exit
from acceptance.run_acceptance import get_executable_path

CMD_SOURCE = [sys.executable, "-m", "pairwise_cli"]

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
def test_acceptance_doctor_output(cmd_target):
    rc, stdout, stderr = run_cli_cmd(cmd_target, ["doctor"], timeout=15)
    assert_successful_exit(rc, stderr)
    assert "PICT Execution      : OK" in stdout, f"Doctor check failed: {stdout}"
