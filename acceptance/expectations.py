"""Shared assertions and helpers for acceptance tests."""
import json
import subprocess
import sys

def run_cli_cmd(cmd_target, args, timeout=15):
    """Runs a CLI command and returns (returncode, stdout, stderr)."""
    full_cmd = cmd_target + args
    try:
        result = subprocess.run(
            full_cmd, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as e:
        return -1, e.stdout or "", e.stderr or f"Timeout after {timeout}s"

def assert_successful_exit(returncode, stderr):
    assert returncode == 0, f"Expected 0 exit code, got {returncode}. Stderr: {stderr}"

def assert_failed_exit(returncode):
    assert returncode != 0, "Expected non-zero exit code"

def parse_json_output(stdout):
    try:
        data = json.loads(stdout.strip())
        return data
    except json.JSONDecodeError as e:
        raise AssertionError(f"Failed to parse JSON output: {e}\nStdout: {stdout}")

def assert_generate_json(data):
    assert "metadata" in data, "JSON output missing metadata block"
    assert "test_cases" in data, "JSON output missing test_cases array"
    
    meta = data["metadata"]
    assert "lb" in meta, "metadata missing 'lb'"
    assert "n" in meta, "metadata missing 'n'"
    assert "verified" in meta, "metadata missing 'verified'"
    
def assert_doctor_output(stdout):
    # Depending on how doctor was implemented
    assert "PICT Execution      : OK" in stdout, "Doctor output missing successful execution marker"
