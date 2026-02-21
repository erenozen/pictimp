"""Acceptance robustness tests for adversarial/malformed inputs."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from acceptance.expectations import run_cli_cmd
from acceptance.run_acceptance import get_executable_path

CMD_SOURCE = [sys.executable, "-m", "pairwise_cli"]
MODEL_PATH = Path(__file__).parent.parent.parent / "examples" / "sample.pict"


def _assert_no_traceback(stdout: str, stderr: str):
    assert "Traceback (most recent call last)" not in stdout
    assert "Traceback (most recent call last)" not in stderr


@pytest.fixture(params=["source", "exe"])
def cmd_target(request):
    if request.param == "source":
        return CMD_SOURCE
    exe_path = get_executable_path()
    if not exe_path:
        pytest.skip("Executable not built")
    return exe_path


@pytest.mark.acceptance
def test_abuse_missing_model_file_no_traceback(cmd_target):
    missing = Path(__file__).parent / "does_not_exist.pict"
    rc, stdout, stderr = run_cli_cmd(
        cmd_target,
        ["generate", "--model", str(missing), "--format", "json"],
        timeout=15,
    )
    assert rc != 0
    assert "File not found" in stderr
    _assert_no_traceback(stdout, stderr)


@pytest.mark.acceptance
def test_abuse_verify_invalid_json_no_traceback(cmd_target, tmp_path):
    bad_json = tmp_path / "bad_cases.json"
    bad_json.write_text("{not-json}", encoding="utf-8")

    rc, stdout, stderr = run_cli_cmd(
        cmd_target,
        ["verify", "--model", str(MODEL_PATH), "--cases", str(bad_json)],
        timeout=15,
    )
    assert rc != 0
    assert "Validation error" in stderr
    _assert_no_traceback(stdout, stderr)


@pytest.mark.acceptance
def test_abuse_verify_empty_csv_no_traceback(cmd_target, tmp_path):
    empty_csv = tmp_path / "empty_cases.csv"
    empty_csv.write_text("", encoding="utf-8")

    rc, stdout, stderr = run_cli_cmd(
        cmd_target,
        ["verify", "--model", str(MODEL_PATH), "--cases", str(empty_csv)],
        timeout=15,
    )
    assert rc != 0
    assert "Cases file is empty" in stderr
    _assert_no_traceback(stdout, stderr)


@pytest.mark.acceptance
def test_abuse_verify_missing_required_column_no_traceback(cmd_target, tmp_path):
    missing_col_csv = tmp_path / "missing_column.csv"
    with open(missing_col_csv, "w", encoding="utf-8", newline="") as f:
        f.write("Language,Color,Display Mode,Fonts\r\n")
        f.write("English,Monochrome,Text-only,Standard\r\n")

    rc, stdout, stderr = run_cli_cmd(
        cmd_target,
        ["verify", "--model", str(MODEL_PATH), "--cases", str(missing_col_csv)],
        timeout=15,
    )
    assert rc == 2
    assert "missing required columns" in stderr
    _assert_no_traceback(stdout, stderr)


@pytest.mark.acceptance
def test_abuse_generate_non_utf8_model_no_traceback(cmd_target, tmp_path):
    bad_model = tmp_path / "bad_model.pict"
    bad_model.write_bytes(b"\xff\xfe\xfa\xfb")

    rc, stdout, stderr = run_cli_cmd(
        cmd_target,
        ["generate", "--model", str(bad_model), "--format", "json"],
        timeout=15,
    )
    assert rc != 0
    assert "UTF-8" in stderr
    _assert_no_traceback(stdout, stderr)
