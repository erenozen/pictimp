# PICT Improved

Cross-platform CLI tool for generating **pairwise (2-way) combinatorial test suites** using Microsoft PICT.

## What it does
- Generates pairwise test cases from `.pict` models
- Verifies pairwise coverage
- Searches for smaller suites across multiple runs/seeds
- Works as a **standalone executable** (PICT is bundled)

## Executables
- **Windows:** `pairwise-cli-win-x64.exe`
- **Linux:** `pairwise-cli-linux-x64` (included in this repository)

No Python or separate PICT installation is required to run the executables.

## [Demo Video](https://drive.google.com/file/d/1GMQX0jZKarXRnUFS3gjtPqyHBvhkJ8lT/view?usp=drive_link) 
In this video (around **1:40**), the first run produces a valid pairwise suite with **17 test cases** (matching the text book’s (Software Testing and Analysis: Process, Principles and Techniques, Wiley, ISBN 0471455938., Mauro Pezzè, Michal Young, 2008, Wiley) result). Then the tool continues trying different randomized PICT runs and finds a **16-case** suite.

Why it can stop at 16 (and why this is **provably minimum**): for pairwise testing, the minimum possible number of test cases is bounded below by the largest number of value-combinations among any single pair of parameters. In other words, if one parameter pair has `v_i × v_j = 16` combinations, then **no pairwise test suite can have fewer than 16 tests**, because each test can cover at most one combination for that specific parameter pair. Therefore, **16 is a mathematical lower bound**.

Since the tool also verifies full pairwise coverage and successfully produces a suite with exactly **16** test cases, it has reached the lower bound. That means the result is **optimal (provably minimum)**, so further search cannot improve it.

## Quick Usage
```bash
# Interactive wizard
./pairwise-cli-linux-x64

# Generate from model
./pairwise-cli-linux-x64 generate --model examples/sample.pict --format table

# Verify a generated suite
./pairwise-cli-linux-x64 verify --model examples/sample.pict --cases cases.csv
````

## Main Commands

* `generate`
* `verify`
* `doctor`
* `version`
* `licenses`

## Repository Notes

The repository includes:

* source code
* tests
* build scripts
* Linux and Windows executables 
