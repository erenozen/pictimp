# PICT Improved

Cross-platform CLI tool for generating **pairwise (2-way) combinatorial test suites** using Microsoft PICT.

## What It Does

If you have a system with multiple parameters, each having multiple values, testing every combination is exponential. Pairwise testing guarantees that **every pair of parameter values** appears in at least one test case. This catches most real-world interaction bugs with far fewer tests.

For example, 5 parameters with 3–4 values each would require **432 exhaustive test cases**. Pairwise testing covers the same interaction space in as few as **16**.

## Executables

- **Windows:** `pairwise-cli-win-x64.exe`
- **Linux:** `pairwise-cli-linux-x64`

No Python or separate PICT installation is required to run the executables.

## Demo Video

[In this video](https://drive.google.com/file/d/1GMQX0jZKarXRnUFS3gjtPqyHBvhkJ8lT/view?usp=drive_link), around **1:40**, the first run produces a valid pairwise suite with **17 test cases** (matching the textbook's result from *Software Testing and Analysis: Process, Principles and Techniques*, Pezze & Young, 2008, Wiley). Then the tool continues trying different randomized PICT runs and finds a **16-case** suite : the **provably minimum**.

## Quick Usage

```bash
# Interactive wizard
./pairwise-cli-linux-x64

# Generate from a model file
./pairwise-cli-linux-x64 generate --model examples/sample.pict --format json --verify

# Verify an existing test suite
./pairwise-cli-linux-x64 verify --model examples/sample.pict --cases cases.csv

# Self-diagnostics
./pairwise-cli-linux-x64 doctor
```

## Building From Source

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v                     # Run all tests
bash scripts/build_exe.sh     # Build standalone executable
```

## Project Structure

```
pairwise_cli/            Application source code (pure Python, zero external dependencies)
├── cli.py               Entry point: argument parsing, 6 subcommands
├── model.py             Data model: Parameter and PairwiseModel classes, .pict file parsing
├── generate.py          Core orchestration: multi-seed loop, early-stop, timeout, determinism
├── verify.py            Coverage verification: checks all pairwise combinations are covered
├── bounds.py            Lower bound computation: theoretical minimum suite size
├── output.py            Output formatting: table, CSV, JSON with metadata
├── pict.py              Platform detection, PICT binary extraction/caching, subprocess execution
├── preflight.py         Pre-flight validation (non-throwing, used by wizard)
├── util.py              Safe name generation for PICT compatibility
└── wizard.py            Interactive wizard mode with menus and editing

tests/                   62 unit/integration tests
tests/acceptance/        20 acceptance tests (run against both source AND compiled executable)
acceptance/              Standalone acceptance runner script
scripts/                 Build scripts (build_exe.sh, build_pict.sh, verify_vendor.py)
vendor/pict/             Pre-built PICT binaries (linux-x64, win-x64)
dist/                    Built standalone executables
examples/sample.pict     Example model file
```

## How Generation Works

1. User provides a `.pict` model file (parameters and values)
2. The app **parses and validates** the model
3. Optionally **reorders parameters** by value count (descending) : this helps PICT produce smaller suites
4. Computes a **mathematical lower bound** (LB) : the theoretical minimum suite size
5. Runs a **multi-seed loop**: executes PICT up to N times (default 50) with different random seeds, each producing a different test suite
6. After each PICT run, **mathematically verifies** that all pairwise combinations are covered
7. Tracks the **smallest verified suite** across all attempts
8. If it finds a suite where N == LB, it **early-stops** : that's provably the minimum possible
9. Outputs the result as table, CSV, or JSON (with full metadata)

**Exit codes:** 0 = success, 2 = validation error, 3 = PICT error, 4 = verification failed, 5 = timeout

## The Math

### The Problem

Given the example model (`examples/sample.pict`):

| Parameter    | Values                                       | Count |
|-------------|----------------------------------------------|-------|
| Language     | English, French, Spanish, Portuguese         | 4     |
| Color        | Monochrome, Color-map, 16-bit, True-color    | 4     |
| Display Mode | Full-graphics, Text-only, Limited-bandwidth  | 3     |
| Fonts        | Standard, Minimal, Document-loaded           | 3     |
| Screen Size  | Laptop, Hand-held, Full-size                 | 3     |

Exhaustive testing: 4 x 4 x 3 x 3 x 3 = **432 test cases**. Pairwise testing covers the same interaction space in as few as **16**.

### Lower Bound (`bounds.py`)

For every pair of parameters (i, j), compute `count_i x count_j`. The **maximum product** is the lower bound : you need at least that many rows to cover that one parameter pair alone.

```
Language x Color        = 4 x 4 = 16  <-- maximum
Language x Display Mode = 4 x 3 = 12
Language x Fonts        = 4 x 3 = 12
Language x Screen Size  = 4 x 3 = 12
Color x Display Mode    = 4 x 3 = 12
Color x Fonts           = 4 x 3 = 12
Color x Screen Size     = 4 x 3 = 12
Display Mode x Fonts    = 3 x 3 =  9
Display Mode x Screen   = 3 x 3 =  9
Fonts x Screen Size     = 3 x 3 =  9

LB = max(16, 12, 12, ..., 9) = 16
```

No test suite can have fewer than 16 rows. When the generator finds exactly 16, it's **provably minimum**.

### Verification (`verify.py`)

For each parameter pair, the algorithm tracks which (value_i, value_j) combinations appear in the test suite. For example, scanning one row:

```
Row: [English, Monochrome, Full-graphics, Standard, Laptop]

  (Language, Color):        mark (English, Monochrome)
  (Language, Display Mode): mark (English, Full-graphics)
  (Language, Fonts):        mark (English, Standard)
  ... and so on for all 10 parameter pairs
```

After scanning all rows, it checks: for every parameter pair, is every value combination covered? If (Language, Color) has 16 expected pairs, all 16 must appear. If any is missing, verification fails.

The total pairs that must be covered: 16+12+12+12+12+12+12+9+9+9 = **115**. Each row covers 10 pairs at once, so 16 rows are enough when overlaps are maximally efficient.

```
Model [4,4,3,3,3]  -->  bounds.py: LB = 16 (theoretical floor)
                              |
                    Multi-seed loop (generate.py)
                    Try seed 0, 1, 2, ... 49
                              |
                    Each seed -> PICT produces N test cases
                    Seed 0: N=17, Seed 1: N=16, Seed 2: N=18
                              |
                    verify.py: all 115 pairs covered? YES
                              |
                    N(16) == LB(16) -> PROVABLY MINIMUM (early-stop)
```

## What I Implemented Beyond PICT

PICT is a binary that takes a model and seed then outputs one test suite. Everything else is implemented by me.

| What | File | Why PICT doesn't do this |
|------|------|--------------------------|
| Pairwise coverage verification | `verify.py` | PICT generates suites but never proves they're correct. Builds a coverage matrix and mathematically verifies every pair is present. |
| Lower bound computation | `bounds.py` | PICT has no concept of "minimum possible." Computes LB = max(vi x vj) : the theoretical floor. |
| Multi-seed optimization loop | `generate.py` | PICT runs once with one seed. This runs it up to 5000 times, tracking the smallest verified suite, with early-stop when LB is hit. |
| Deterministic tie-breaking | `generate.py` | When two seeds produce the same N, `--deterministic` guarantees the lower seed wins : reproducible builds. |
| Parameter reordering (auto mode) | `model.py` | Sorting parameters by value count (descending) before feeding to PICT produces smaller suites. |
| Complete data model with validation | `model.py` | Safe name generation, case-insensitive duplicate detection, special character validation, serialization/deserialization. |
| Pre-flight validation system | `preflight.py` | Non-throwing validation that collects all issues at once. Used by the wizard for user-friendly error reporting. |
| Full CLI with 6 subcommands | `cli.py` | generate, verify, doctor, wizard, licenses, version : with structured exit codes (0/2/3/4/5). |
| Interactive wizard mode | `wizard.py` | Build models interactively, edit/delete parameters, choose settings, save outputs : with full error recovery. |
| Output formatting (table/CSV/JSON) | `output.py` | JSON includes a metadata block with lb, n, seed, verified, ordering_mode. PICT only outputs raw TSV. |
| Cross-platform binary management | `pict.py` | Bundled vendor binaries, cache extraction with 4-level fallback, PyInstaller bundle support, platform detection. |
| Two-tier timeout system | `generate.py` | Per-PICT-execution timeout and total generation budget. PICT has no timeout concept. |
| 82 automated tests | `tests/` | Unit, integration, acceptance (source+exe), hypothesis fuzzing, wizard adversarial tests. |
| CI/CD pipeline | `.github/workflows/` | GitHub Actions building for Windows and Linux, running tests, uploading artifacts. |
| PyInstaller packaging | `scripts/` | Build scripts that bundle Python and PICT into a single standalone executable. |

## Test Suite

**82 tests total** (62 unit/integration and 20 acceptance).

### Unit & Integration Tests (`tests/`)

| File | Tests | What it tests | Real PICT or Mocked? |
|------|-------|--------------|---------------------|
| `test_bounds.py` | 4 | Lower bound math: empty, single, two, multiple params | Pure math |
| `test_verify.py` | 2 | Coverage verification: complete suite passes, incomplete detects missing | Pure math |
| `test_model.py` | 5 | Safe names, serialization, parsing, counts, reordering | Pure logic |
| `test_output_parse.py` | 3 | TSV parsing, column reordering, empty input | Pure logic |
| `test_pict_select.py` | 4 | Platform detection: Win, Linux, macOS (error), FreeBSD (error) | Mocked platform |
| `test_filesystem.py` | 2 | Cache fallback to temp dir, complete failure raises error | Mocked filesystem |
| `test_determinism.py` | 2 | Deterministic tie-breaking, require_verified drops unverified | Mocked PICT |
| `test_generate_contract.py` | 2 | Best failing attempt reporting, verify=False behavior | Mocked PICT |
| `test_fuzz.py` | 3 | Hypothesis fuzzing: valid models (100x), garbage input (200x), limit check | Hypothesis |
| `test_cli_contract.py` | 16 | Full CLI: flags, validation, timeouts, verify roundtrip, BOM, CRLF | Real PICT |
| `test_integration_sample.py` | 1 | End-to-end with sample.pict: N >= 16, verified=True | Real PICT |
| `test_wizard_mock.py` | 18 | Wizard: input, retries, save, errors, EOF, Ctrl+C, duplicates | Mocked I/O |

### Acceptance Tests (`tests/acceptance/`)

Every acceptance test runs **twice** : once against the Python source and once against the compiled executable.

| File | Tests | What it tests |
|------|-------|--------------|
| `test_acceptance_doctor.py` | 2 | Doctor command succeeds |
| `test_acceptance_generate.py` | 4 | Generate with auto and keep ordering, N >= 16, verified |
| `test_acceptance_determinism.py` | 2 | Two identical runs produce identical output |
| `test_acceptance_verify.py` | 2 | Incomplete cases correctly fail verification |
| `test_acceptance_abuse.py` | 10 | Error paths: missing model, invalid JSON, empty CSV, missing columns, non-UTF8 : clean errors, no tracebacks |

## Verification Checklist

See `docs/VERIFICATION_CHECKLIST.md`
