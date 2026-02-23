# Verification Checklist (pairwise-cli)

Manual checklist to verify correctness, truthfulness, and robustness.

Supported platforms: **Windows x64** and **Linux x64** only.  
System-wide Microsoft PICT installation is **not required**.

Exit code capture:
- Linux: `echo $?`
- Windows PowerShell: `$LASTEXITCODE`

## A) Preconditions

**Command**
```bash
ls -l dist
ls -l examples/sample.pict
```

**Expected Result**
- Linux artifact exists: `dist/pairwise-cli-linux-x64`
- Windows artifact exists on Windows builds: `dist/pairwise-cli-win-x64.exe`
- Sample model exists: `examples/sample.pict`

**What this proves**
- Build artifacts and grading model are present.

---

## B) Smoke Test: doctor

**Command (Linux)**
```bash
./dist/pairwise-cli-linux-x64 doctor
echo $?
```
Windows note: run `.\dist\pairwise-cli-win-x64.exe doctor` and check `$LASTEXITCODE`.

**Expected Result**
- Exit code `0`
- Output indicates bundled PICT extraction and execution succeeded (for example, `PICT Execution : OK`)
- Doctor performs real PICT invocation (not only file checks)

**What this proves**
- Bundled/no-download distribution works end-to-end at runtime.

---

## C) Generate (Verified, deterministic, auto-order)

**Command (Linux)**
```bash
./dist/pairwise-cli-linux-x64 generate --model examples/sample.pict --format json --verify --early-stop --ordering auto --tries 200 --seed 0 --deterministic > out.json
echo $?
```

**JSON validation (choose one)**
Optional helper:
```bash
jq -e . out.json >/dev/null && echo "JSON OK"
```
Portable fallback:
```bash
python - <<'PY'
import json
json.load(open("out.json","r",encoding="utf-8"))
print("JSON OK")
PY
```

**Expected Result**
- Exit code `0`
- Stdout is valid JSON only
- `metadata.verified == true`
- `metadata.ordering_mode == "auto"` (or equivalent auto marker)
- `metadata.n >= 16`
- `metadata.lb == 16` (sample model, strength 2)
- If any UI output claims `PROVABLY MINIMUM`, then `n == lb == 16`

**What this proves**
- Verified generation path, truthful minimum claim gating, and JSON-output contract.

---

## D) Truthfulness Check: no-verify

**Command**
```bash
./dist/pairwise-cli-linux-x64 generate --model examples/sample.pict --format json --no-verify > out_noverify.json
echo $?
python - <<'PY'
import json
p=json.load(open("out_noverify.json","r",encoding="utf-8"))
print(p["metadata"]["verified"])
PY
```

**Expected Result**
- Exit code `0`
- `metadata.verified` is `false`
- No false proof/minimum claim in human-mode outputs (if checked)

**What this proves**
- Verification metadata is truthful.

---

## E) JSON Purity Under Verbose Logging

**Command**
```bash
./dist/pairwise-cli-linux-x64 generate --model examples/sample.pict --format json --verbose > out_verbose.json 2> out_verbose.err
echo $?
python - <<'PY'
import json
json.load(open("out_verbose.json","r",encoding="utf-8"))
print("JSON OK")
PY
```

**Expected Result**
- Exit code `0`
- Stdout parses as JSON
- Logs/progress appear on stderr (`out_verbose.err`), not in JSON stdout

**What this proves**
- Machine-readable JSON purity even with verbose mode.

---

## F) Validation Error Path (Exit 2)

**Command 1: invalid strength**
```bash
./dist/pairwise-cli-linux-x64 generate --model examples/sample.pict --strength 1
echo $?
```

**Command 2: invalid tries bound**
```bash
./dist/pairwise-cli-linux-x64 generate --model examples/sample.pict --tries 999999 --max-tries 10
echo $?
```

**Expected Result**
- Both exit with code `2`
- Clear validation errors on stderr

**What this proves**
- Input validation contract is enforced.

---

## G) Timeout Error Paths (Exit 5)

**Command 1: tiny per-PICT timeout**
```bash
./dist/pairwise-cli-linux-x64 generate --model examples/sample.pict --pict-timeout-sec 0.001 --tries 50 --format json
echo $?
```

**Command 2: tiny total timeout**
```bash
./dist/pairwise-cli-linux-x64 generate --model examples/sample.pict --total-timeout-sec 0.01 --tries 500 --format json
echo $?
```

**Expected Result**
- Exit code `5`
- Timeout-related error text

**What this proves**
- Timeout semantics and exit-code mapping are correct.

---

## H) Verification Failure Path (Exit 4) — Conditional

**Step 1: check verify subcommand availability**
```bash
./dist/pairwise-cli-linux-x64 --help | grep -q " verify " && echo "verify-subcommand-present" || echo "verify-subcommand-missing"
```

**If verify subcommand is present (preferred)**
```bash
./dist/pairwise-cli-linux-x64 verify --model examples/sample.pict --cases acceptance/fixtures/incomplete_cases.csv
echo $?
```

**If verify subcommand is missing (fallback evidence)**
```bash
pytest -m acceptance -q tests/acceptance/test_acceptance_verify.py
```

**Expected Result**
- Preferred path: exit code `4` and missing-pair preview (first 20 max)
- Fallback path: acceptance negative verification test passes

**What this proves**
- Verification failure semantics and diagnostics are correct.

---

## I) Determinism / Reproducibility

**Command**
```bash
./dist/pairwise-cli-linux-x64 generate --model examples/sample.pict --format json --verify --early-stop --ordering auto --tries 200 --seed 123 --deterministic > out1.json
./dist/pairwise-cli-linux-x64 generate --model examples/sample.pict --format json --verify --early-stop --ordering auto --tries 200 --seed 123 --deterministic > out2.json
diff -u out1.json out2.json
```
Windows note: use `Compare-Object (Get-Content out1.json) (Get-Content out2.json)`.

**Expected Result**
- No diff (identical JSON)

**What this proves**
- Deterministic seed sequence and stable output selection/serialization.

---

## J) Acceptance Pack (Repo-level evidence)

**Command**
```bash
pytest -m acceptance -q
python acceptance/run_acceptance.py --mode source --timeout-sec 60
python acceptance/run_acceptance.py --mode exe --timeout-sec 60
```

**Expected Result**
- All acceptance checks pass

**What this proves**
- End-to-end black-box regression coverage passes in both source and executable modes.

---

## K) Exit Code Reference

| Exit | Meaning |
|---|---|
| 0 | Success |
| 2 | Validation/platform error |
| 3 | PICT/execution error (non-timeout) |
| 4 | Verification failure |
| 5 | Timeout |

---

## Strength != 2 semantics (include in grading)

**Command**
```bash
./dist/pairwise-cli-linux-x64 generate --model examples/sample.pict --strength 3 --format json > out_s3.json
echo $?
python - <<'PY'
import json
p=json.load(open("out_s3.json","r",encoding="utf-8"))
print(p["metadata"]["lb"])
PY
```

**Expected Result**
- Exit code `0`
- `metadata.lb` is `null` . JSON field metadata.lb is null (Python print output will show None)
- No human minimum/LB claim for non-2 strength modes

**What this proves**
- LB/minimum contract is correctly restricted to strength 2.

---

## Common Failure Diagnosis

- JSON parse fails in `--format json --verbose`: logs leaked to stdout.
- Timeout returns `3` instead of `5`: timeout mapping bug.
- `verified=true` with `--no-verify`: truthfulness bug.
- “PROVABLY MINIMUM” while unverified: minimum-claim gating bug.
