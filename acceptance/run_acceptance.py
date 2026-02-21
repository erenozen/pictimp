"""Runner script for pairwsise-cli Acceptance Testing."""
import os
import sys
import platform
import argparse
from pathlib import Path

# Add project root to path so we can import expectations
sys.path.insert(0, str(Path(__file__).parent.parent))
from acceptance.expectations import run_cli_cmd, assert_successful_exit, parse_json_output, assert_generate_json

def get_executable_path():
    """Detect platform and find the proper built executable in dist/."""
    system = platform.system().lower()
    
    if system == "windows":
        filename = "pairwise-cli-win-x64.exe"
    elif system == "linux":
        filename = "pairwise-cli-linux-x64"
    else:
        return None
        
    dist_dir = Path(__file__).parent.parent / "dist"
    exe_path = dist_dir / filename
    
    if exe_path.exists():
        return [str(exe_path)]
    return None

def run_tests_for_target(name, cmd_target, timeout=15, verbose=False):
    print(f"=== Running Acceptance Tests for target: {name} ===")
    
    repo_root = Path(__file__).parent.parent
    model_path = repo_root / "examples" / "sample.pict"
    
    passed = 0
    failed = 0
    
    tests = [
        ("A) DOCTOR", test_doctor, {}),
        ("B) GENERATE (auto)", test_generate_auto, {'model_path': model_path}),
        ("C) GENERATE (keep)", test_generate_keep, {'model_path': model_path}),
        ("D) DETERMINISM", test_determinism, {'model_path': model_path}),
        ("E) COVERAGE SELF-CHECK", test_coverage_self_check, {'model_path': model_path}),
    ]
    
    for test_name, test_func, kwargs in tests:
        if verbose:
            print(f"  Running {test_name}...")
        try:
            test_func(cmd_target, timeout, **kwargs)
            print(f"  [PASS] {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {test_name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {test_name}: {e}")
            failed += 1
            
    print(f"--- {name} Results: {passed} passed, {failed} failed ---")
    return failed == 0

def test_doctor(cmd_target, timeout):
    rc, stdout, stderr = run_cli_cmd(cmd_target, ["doctor"], timeout=timeout)
    assert_successful_exit(rc, stderr)
    assert "PICT Execution      : OK" in stdout, f"Doctor check failed: {stdout}"

def test_generate_auto(cmd_target, timeout, model_path):
    args = [
        "generate", "--model", str(model_path), "--ordering", "auto", 
        "--strength", "2", "--tries", "40", "--seed", "0", 
        "--verify", "--early-stop", "--deterministic", "--format", "json"
    ]
    rc, stdout, stderr = run_cli_cmd(cmd_target, args, timeout=timeout)
    assert_successful_exit(rc, stderr)
    
    data = parse_json_output(stdout)
    assert_generate_json(data)
    
    meta = data["metadata"]
    assert meta["lb"] == 16, f"Expected LB=16, got {meta['lb']}"
    assert meta["n"] >= 16, f"Expected N>=16, got {meta['n']}"
    assert meta["verified"] is True, "Expected verified=True"

def test_generate_keep(cmd_target, timeout, model_path):
    args = [
        "generate", "--model", str(model_path), "--ordering", "keep", 
        "--strength", "2", "--tries", "40", "--seed", "0", 
        "--verify", "--early-stop", "--deterministic", "--format", "json"
    ]
    rc, stdout, stderr = run_cli_cmd(cmd_target, args, timeout=timeout)
    assert_successful_exit(rc, stderr)
    
    data = parse_json_output(stdout)
    assert_generate_json(data)
    
    meta = data["metadata"]
    assert meta["lb"] == 16, f"Expected LB=16, got {meta['lb']}"
    assert meta["n"] >= 16, f"Expected N>=16, got {meta['n']}"
    assert meta["verified"] is True, "Expected verified=True"

def test_determinism(cmd_target, timeout, model_path):
    args = [
        "generate", "--model", str(model_path), "--ordering", "auto", 
        "--strength", "2", "--tries", "40", "--seed", "123", 
        "--verify", "--early-stop", "--deterministic", "--format", "json"
    ]
    rc1, stdout1, stderr1 = run_cli_cmd(cmd_target, args, timeout=timeout)
    assert_successful_exit(rc1, stderr1)
    
    rc2, stdout2, stderr2 = run_cli_cmd(cmd_target, args, timeout=timeout)
    assert_successful_exit(rc2, stderr2)
    
    data1 = parse_json_output(stdout1)
    data2 = parse_json_output(stdout2)
    
    assert data1["metadata"] == data2["metadata"], "Metadata mismatch across runs"
    assert data1["test_cases"] == data2["test_cases"], "Generated cases mismatch across runs"

def test_coverage_self_check(cmd_target, timeout, model_path):
    # generate an incomplete cases file 
    repo_root = Path(__file__).parent.parent
    cases_path = repo_root / "acceptance" / "fixtures" / "incomplete_cases.csv"
    
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    with cases_path.open("w", encoding="utf-8") as f:
        f.write("Language,Color,Display Mode,Fonts,Screen Size\n")
        f.write("English,Monochrome,Text-only,Standard,Laptop\n")
        
    args = ["verify", "--model", str(model_path), "--cases", str(cases_path)]
    rc, stdout, stderr = run_cli_cmd(cmd_target, args, timeout=timeout)
    
    # Expected to fail coverage
    assert rc != 0, f"Expected verify test to fail correctly, but got exit={rc}"
    assert "Coverage verification failed." in stderr, f"Missing stderr error tracking coverage: {stderr}"

def main():
    parser = argparse.ArgumentParser(description="Run Acceptance Tests.")
    parser.add_argument("--mode", choices=["source", "exe", "both"], default="both", help="Target mode to test")
    parser.add_argument("--timeout-sec", type=int, default=30, help="Timeout per command")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    targets = []
    if args.mode in ("source", "both"):
        targets.append(("Source Module", [sys.executable, "-m", "pairwise_cli"]))
        
    if args.mode in ("exe", "both"):
        exe_path = get_executable_path()
        if exe_path:
            targets.append(("Executable Binary", exe_path))
        else:
            print("Warning: Executable not found in dist/. Skipping Executable targets.")
            if args.mode == "exe":
                sys.exit(1)
                
    all_passed = True
    for name, cmd_target in targets:
        success = run_tests_for_target(name, cmd_target, timeout=args.timeout_sec, verbose=args.verbose)
        if not success:
            all_passed = False
            
    if all_passed:
        print("ALL ACCEPTANCE TESTS PASSED.")
        sys.exit(0)
    else:
        print("SOME ACCEPTANCE TESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
