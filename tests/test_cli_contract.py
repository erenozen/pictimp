"""CLI contract regression tests."""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MODEL_PATH = REPO_ROOT / "examples" / "sample.pict"
CMD = [sys.executable, "-m", "pairwise_cli"]


def run_cli(args, timeout=20):
    return subprocess.run(CMD + args, capture_output=True, text=True, timeout=timeout)

def assert_no_traceback(result):
    assert "Traceback (most recent call last)" not in result.stdout
    assert "Traceback (most recent call last)" not in result.stderr


def generate_csv_cases(tmp_path):
    csv_path = tmp_path / "generated_cases.csv"
    result = run_cli(
        [
            "generate",
            "--model",
            str(MODEL_PATH),
            "--format",
            "csv",
            "--out",
            str(csv_path),
            "--verify",
            "--early-stop",
            "--ordering",
            "auto",
            "--tries",
            "100",
            "--seed",
            "0",
            "--deterministic",
        ],
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert csv_path.exists()
    assert_no_traceback(result)
    return csv_path


def test_generate_accepts_verify_and_early_stop_flags():
    result = run_cli(
        [
            "generate",
            "--model",
            str(MODEL_PATH),
            "--verify",
            "--early-stop",
            "--ordering",
            "auto",
            "--tries",
            "5",
            "--seed",
            "0",
            "--deterministic",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["metadata"]["verified"] is True


def test_strength_must_be_gte_two():
    result = run_cli(
        [
            "generate",
            "--model",
            str(MODEL_PATH),
            "--strength",
            "1",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 2
    assert "--strength must be >= 2" in result.stderr


def test_tries_must_respect_max_tries():
    result = run_cli(
        [
            "generate",
            "--model",
            str(MODEL_PATH),
            "--tries",
            "11",
            "--max-tries",
            "10",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 2
    assert "--tries must be between 1 and 10" in result.stderr


def test_timeout_arguments_must_be_positive():
    result = run_cli(
        [
            "generate",
            "--model",
            str(MODEL_PATH),
            "--pict-timeout-sec",
            "0",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 2
    assert "--pict-timeout-sec must be > 0" in result.stderr

    result = run_cli(
        [
            "generate",
            "--model",
            str(MODEL_PATH),
            "--total-timeout-sec",
            "0",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 2
    assert "--total-timeout-sec must be > 0" in result.stderr


def test_total_timeout_warning_when_lower_than_pict_timeout():
    result = run_cli(
        [
            "generate",
            "--model",
            str(MODEL_PATH),
            "--dry-run",
            "--total-timeout-sec",
            "0.2",
            "--pict-timeout-sec",
            "1.0",
        ]
    )
    assert result.returncode == 0
    assert "Warning: --total-timeout-sec is lower than --pict-timeout-sec" in result.stderr


def test_no_verify_sets_verified_false():
    result = run_cli(
        [
            "generate",
            "--model",
            str(MODEL_PATH),
            "--no-verify",
            "--tries",
            "1",
            "--seed",
            "0",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["metadata"]["verified"] is False


def test_json_output_stays_pure_when_verbose():
    result = run_cli(
        [
            "generate",
            "--model",
            str(MODEL_PATH),
            "--verify",
            "--early-stop",
            "--tries",
            "3",
            "--seed",
            "0",
            "--deterministic",
            "--format",
            "json",
            "--verbose",
        ]
    )
    assert result.returncode == 0, result.stderr
    json.loads(result.stdout)


def test_all_attempt_timeouts_exit_with_timeout_code():
    result = run_cli(
        [
            "generate",
            "--model",
            str(MODEL_PATH),
            "--tries",
            "3",
            "--pict-timeout-sec",
            "0.000001",
            "--total-timeout-sec",
            "1.0",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 5


def test_total_timeout_budget_exit_with_timeout_code():
    result = run_cli(
        [
            "generate",
            "--model",
            str(MODEL_PATH),
            "--tries",
            "50",
            "--pict-timeout-sec",
            "1.0",
            "--total-timeout-sec",
            "0.000001",
            "--format",
            "json",
        ]
    )
    assert result.returncode == 5


def test_verify_roundtrip_generated_csv_succeeds_no_traceback(tmp_path):
    csv_path = generate_csv_cases(tmp_path)

    result = run_cli(["verify", "--model", str(MODEL_PATH), "--cases", str(csv_path)], timeout=30)
    assert result.returncode == 0, result.stderr
    assert "Coverage verified successfully." in result.stderr
    assert_no_traceback(result)


def test_verify_bom_header_csv_succeeds_no_traceback(tmp_path):
    csv_path = generate_csv_cases(tmp_path)
    bom_path = tmp_path / "generated_cases_bom.csv"
    bom_path.write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8-sig")

    result = run_cli(["verify", "--model", str(MODEL_PATH), "--cases", str(bom_path)], timeout=30)
    assert result.returncode == 0, result.stderr
    assert_no_traceback(result)


def test_verify_missing_required_column_returns_validation_no_traceback(tmp_path):
    missing_col = tmp_path / "missing_col.csv"
    with open(missing_col, "w", encoding="utf-8", newline="") as f:
        f.write("Language,Color,Display Mode,Fonts\r\n")
        f.write("English,Monochrome,Text-only,Standard\r\n")

    result = run_cli(["verify", "--model", str(MODEL_PATH), "--cases", str(missing_col)], timeout=30)
    assert result.returncode == 2
    assert "Validation error: missing required columns: Screen Size" in result.stderr
    assert_no_traceback(result)


def test_verify_csv_blank_rows_ignored_no_traceback(tmp_path):
    csv_path = generate_csv_cases(tmp_path)
    blank_rows = tmp_path / "with_blank_rows.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    with open(blank_rows, "w", encoding="utf-8", newline="") as f:
        for i, line in enumerate(lines):
            f.write(line + "\r\n")
            if i > 0:
                f.write("   \t  \r\n")

    result = run_cli(["verify", "--model", str(MODEL_PATH), "--cases", str(blank_rows)], timeout=30)
    assert result.returncode == 0, result.stderr
    assert_no_traceback(result)


def test_verify_invalid_cell_value_returns_validation_no_traceback(tmp_path):
    csv_path = generate_csv_cases(tmp_path)
    invalid_value_csv = tmp_path / "invalid_value.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 1
    first_row = lines[1].split(",")
    first_row[0] = "INVALID_LANGUAGE"
    lines[1] = ",".join(first_row)
    with open(invalid_value_csv, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")

    result = run_cli(["verify", "--model", str(MODEL_PATH), "--cases", str(invalid_value_csv)], timeout=30)
    assert result.returncode == 2
    assert "Validation error:" in result.stderr
    assert_no_traceback(result)


def test_verify_csv_extra_columns_ignored_if_required_present(tmp_path):
    csv_path = generate_csv_cases(tmp_path)
    extra_col_csv = tmp_path / "with_extra_col.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    with open(extra_col_csv, "w", encoding="utf-8", newline="") as f:
        for i, line in enumerate(lines):
            if i == 0:
                f.write(line + ",Extra Column\r\n")
            else:
                f.write(line + ",extra\r\n")

    result = run_cli(["verify", "--model", str(MODEL_PATH), "--cases", str(extra_col_csv)], timeout=30)
    assert result.returncode == 0, result.stderr
    assert_no_traceback(result)


def test_verify_generated_csv_windows_double_crlf_style_no_traceback(tmp_path):
    csv_path = generate_csv_cases(tmp_path)
    double_crlf_csv = tmp_path / "double_crlf.csv"
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    with open(double_crlf_csv, "wb") as f:
        f.write(("\r\r\n".join(lines) + "\r\r\n").encode("utf-8"))

    result = run_cli(["verify", "--model", str(MODEL_PATH), "--cases", str(double_crlf_csv)], timeout=30)
    assert result.returncode == 0, result.stderr
    assert_no_traceback(result)
