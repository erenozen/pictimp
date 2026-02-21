"""Acceptance tests for standalone verify command."""
import pytest
import sys
from pathlib import Path

# Add project root to path so we can import expectations
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from acceptance.expectations import run_cli_cmd
from acceptance.run_acceptance import get_executable_path

CMD_SOURCE = [sys.executable, "-m", "pairwise_cli"]
MODEL_PATH = Path(__file__).parent.parent.parent / "examples" / "sample.pict"
FIXTURE_PATH = Path(__file__).parent.parent.parent / "acceptance" / "fixtures" / "incomplete_cases.csv"

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
def test_acceptance_coverage_self_check(cmd_target, tmp_path):
    # generate an incomplete cases file 
    cases_path = FIXTURE_PATH
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    with cases_path.open("w", encoding="utf-8") as f:
        f.write("Language,Color,Display Mode,Fonts,Screen Size\n")
        f.write("English,Monochrome,Text-only,Standard,Laptop\n")
        
    args = ["verify", "--model", str(MODEL_PATH), "--cases", str(cases_path)]
    rc, stdout, stderr = run_cli_cmd(cmd_target, args, timeout=15)
    
    assert rc != 0, f"Expected verify test to fail correctly, but got exit={rc}"
    assert "Coverage verification failed." in stderr, f"Missing stderr error tracking coverage: {stderr}"
