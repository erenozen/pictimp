# Pairwise-CLI

A complete, cross-platform CLI application for generating pairwise (2-way) combinatorial test suites using Microsoft PICT.

## Overview
Pairwise testing is a combinatorics-based method of software testing that, for each pair of input parameters, tests all possible discrete combinations of those parameters. This ensures that any bugs caused by the interaction of two parameters will be caught, drastically reducing the number of tests compared to exhaustive testing while maintaining high coverage.

## Pairwise Minimums
A core feature of `pairwise-cli` is the computation of the theoretical pairwise **Lower Bound (LB)**.
For an unordered pair of parameters i, j with value counts v_i, v_j, the number of possible pairs is v_i * v_j.
The absolute minimum number of tests needed to cover ALL pairs in the model is the maximum of these products:
`LB = max(v_i * v_j)` for all parameters i < j.

If the generated suite size `N` equals `LB`, we can definitively say the suite is **PROVABLY MINIMUM**.

To achieve this, `pairwise-cli` continuously runs PICT with different random seeds (up to 50 tries by default). If it finds a suite where `N == LB`, it stops early, guaranteeing the most mathematically optimal test suite possible.

It also automatically reorders parameters inside the PICT engine (largest domain first) without altering your output format, maximizing the collision rate of pairs to decrease test suite sizes.

Finally, `pairwise-cli` strictly verifies mathematical coverage of all required pairwise combinations before outputting a test suite, ensuring absolute safety for mission-critical tests.

## Installation
Just download the pre-compiled executable for your platform from the Releases page. No installation required. You do NOT need to install PICT!

- `pairwise-cli-win-x64.exe`
- `pairwise-cli-linux-x64`
- `pairwise-cli-macos-x64`
- `pairwise-cli-macos-arm64`

### Usage
Run the wizard directly without arguments:
```bash
./pairwise-cli-linux-x64
```
It will guide you through entering parameters interactively.

Generate tests non-interactively from a `.pict` model file:
```bash
./pairwise-cli-linux-x64 generate --model examples/sample.pict --format table
```
*Formats:* `table`, `csv`, `json`.

*Optimization and Verification flags for `generate`:*
- `--ordering {keep,auto}`: Choose parameter ordering (Default: `auto`). Reorders parameters descending by value count to generate smaller test suites while mapped output remains canonical.
- `--tries N`: Best-of search iterations using randomized seeds to find the smallest possible valid test suite (Default: `50`).
- `--early-stop` / `--no-early-stop`: Stop immediately if a mathematically minimum test suite `N == LB` is found (Default: True).
- `--verify` / `--no-verify`: Statistically verify that every single valid 2-way pair is perfectly covered in the final output (Default: True).
- `--seed N`: Start with a base random seed.

Other commands:
- `doctor`: Verifies bundled PICT extraction and system compatibility.
- `version`: Prints the app version.
- `licenses`: Prints open-source licenses.

## Building from source

### 1) Build vendor PICT
This compiles PICT and places it into `vendor/pict/<arch>/`.

**Linux / macOS:**
```bash
./scripts/build_pict.sh
```
**Windows:**
```powershell
.\scripts\build_pict.ps1
```

### 2) Run Tests
```bash
pip install -e .[dev]
pytest -v
```

### 3) Package Executable
This bundles the PICT binary and python files into a single standalone executable.
**Linux / macOS:**
```bash
./scripts/build_exe.sh
```
**Windows:**
```powershell
.\scripts\build_exe.ps1
```
