# Pairwise-CLI Acceptance Testing

This directory contains standalone, end-to-end acceptance tests that prove the correctness and reproducibility of the `pairwise-cli` tool.

These tests execute the CLI as a fully isolated subprocess, evaluating real command-line arguments and interpreting `stdout`, `stderr`, and `exit_codes`. They are designed to be run against both the raw Python source code and compiled executable binaries (e.g., PyInstaller outputs).

## Test Matrix
The acceptance test suite automatically runs the following verification tracks:
1. **DOCTOR Output Checks**: Verifies that Microsoft PICT is properly bundled, caches correctly, and executes without errors natively confirming extraction paths.
2. **GENERATE (Auto / Keep)**: Generates combinatorial datasets using `examples/sample.pict`, verifying mathematically that `N >= LB`, that valid JSON structural outputs are rendered, and that generated arrays genuinely provide subset coverage verification.
3. **DETERMINISM Track**: Executes generation routines multiple times enforcing exact constraints (Seed selection, Tries depth, Re-ordering behaviors) and asserting deep equality across JSON metadata outputs.
4. **COVERAGE SELF-CHECK**: Validates the isolated `verify` subcommand using incomplete CSV test suites explicitly forcing validation routines to fail correctly and list missing mappings.

## How to Run
There are two ways to invoke the acceptance test suite:

### 1. Using the Runner Script
A standalone cross-platform Python runner detects your built binaries and executes the suite without requiring standard testing libraries.

```bash
# Run tests against both python source and compiled executable binary (if found in dist/)
python acceptance/run_acceptance.py

# Run only against the compiled binary
python acceptance/run_acceptance.py --mode exe

# Run explicitly against pure python source
python acceptance/run_acceptance.py --mode source
```

### 2. Using PyTest 
The acceptance tests are also natively wired into the main `pytest` tree using markers. They will automatically invoke and use fixtures to detect whether a local development source or standard binary applies.

```bash
# Run all acceptance tests explicitly
pytest -m acceptance -v
```
