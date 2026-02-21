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
