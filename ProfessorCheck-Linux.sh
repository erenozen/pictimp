#!/usr/bin/env bash
# pairwise-cli professor-style automated check suite (Linux Bash)
# IMPORTANT:
# - This suite intentionally uses direct native invocation ("$EXE" args...) and file redirection
#   to preserve argument integrity and avoid shell quoting corruption.
# - This suite covers CLI robustness/contracts. Manual wizard abuse testing is still recommended.

# Bash settings:
# - Do NOT use `set -e` globally here because the harness intentionally executes commands that
#   are expected to fail (validation, timeout, malformed-input checks) and records their exit codes.
set -u
set -o pipefail

# ------------------------------
# Defaults / CLI args
# ------------------------------
EXE_PATH="./dist/pairwise-cli-linux-x64"
MODEL_PATH="./examples/sample.pict"
VERIFY_FIXTURE_PATH="./acceptance/fixtures/incomplete_cases.csv"

print_usage() {
  cat <<'USAGE'
Usage:
  ./ProfessorCheck-Linux.sh [--exe-path PATH] [--model-path PATH] [--verify-fixture-path PATH]

Options:
  --exe-path PATH             Path to Linux executable (default: ./dist/pairwise-cli-linux-x64)
  --model-path PATH           Path to sample model (default: ./examples/sample.pict)
  --verify-fixture-path PATH  Path to incomplete verify fixture CSV (default: ./acceptance/fixtures/incomplete_cases.csv)
  -h, --help                  Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --exe-path)
      EXE_PATH="${2:-}"; shift 2 ;;
    --model-path)
      MODEL_PATH="${2:-}"; shift 2 ;;
    --verify-fixture-path)
      VERIFY_FIXTURE_PATH="${2:-}"; shift 2 ;;
    -h|--help)
      print_usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      print_usage >&2
      exit 2 ;;
  esac
done

# ------------------------------
# Globals / temp files
# ------------------------------
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
TEMP_DIR="$(mktemp -d -t pairwise-profcheck-XXXXXXXXXX)"
LAST_STDOUT="$TEMP_DIR/last_stdout.txt"
LAST_STDERR="$TEMP_DIR/last_stderr.txt"
LAST_RC=-999
LAST_CMD=""

# Python for JSON parsing helper
JSON_PYTHON=""
if command -v python3 >/dev/null 2>&1; then
  JSON_PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  JSON_PYTHON="$(command -v python)"
fi

# ------------------------------
# Output helpers
# ------------------------------
hr() {
  printf '%s\n' "------------------------------------------------------------"
}

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf '\033[32mPASS:\033[0m %s\n' "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf '\033[31mFAIL:\033[0m %s\n' "$1"
}

skip() {
  SKIP_COUNT=$((SKIP_COUNT + 1))
  printf '\033[33mSKIP:\033[0m %s\n' "$1"
}

# ------------------------------
# Path / file helpers
# ------------------------------
resolve_path_safe() {
  local p="${1:-}"
  if [[ -z "${p//[[:space:]]/}" ]]; then
    printf '%s\n' "$p"
    return 0
  fi

  if [[ "$p" != /* ]]; then
    p="$SCRIPT_DIR/$p"
  fi

  if command -v realpath >/dev/null 2>&1; then
    realpath -m -- "$p" 2>/dev/null || printf '%s\n' "$p"
  elif [[ -n "$JSON_PYTHON" ]]; then
    "$JSON_PYTHON" - "$p" <<'PY' 2>/dev/null || printf '%s\n' "$p"
import os, sys
print(os.path.abspath(sys.argv[1]))
PY
  else
    printf '%s\n' "$p"
  fi
}

write_text_file() {
  local path="$1"
  local text="${2-}"
  printf '%s' "$text" >"$path"
}

print_file_first20_prefixed() {
  local path="$1"
  if [[ -f "$path" ]]; then
    awk 'NR<=20 { print "    " $0 }' "$path"
  fi
}

# ------------------------------
# Assertions
# ------------------------------
assert_file_exists() {
  local path="$1"
  local name="$2"
  if [[ -e "$path" ]]; then
    pass "$name"
  else
    fail "$name (missing: $path)"
  fi
}

assert_file_non_empty() {
  local path="$1"
  local name="$2"
  if [[ -s "$path" ]]; then
    pass "$name"
  else
    fail "$name (empty/missing: $path)"
  fi
}

assert_contains() {
  local path="$1"
  local needle="$2"
  local name="$3"
  local ci="${4:-0}"  # 1 => case-insensitive

  if [[ ! -f "$path" ]]; then
    fail "$name (file missing: $path)"
    return
  fi

  local ok=1
  if [[ "$ci" == "1" ]]; then
    if grep -Fqi -- "$needle" "$path"; then ok=0; fi
  else
    if grep -Fq -- "$needle" "$path"; then ok=0; fi
  fi

  if [[ $ok -eq 0 ]]; then
    pass "$name"
  else
    fail "$name (missing '$needle')"
    print_file_first20_prefixed "$path"
  fi
}

assert_not_contains() {
  local path="$1"
  local needle="$2"
  local name="$3"

  # If stderr/output file doesn't exist, that's fine for "no traceback" checks.
  if [[ ! -f "$path" ]]; then
    pass "$name"
    return
  fi

  if grep -Fq -- "$needle" "$path"; then
    fail "$name (found forbidden '$needle')"
    print_file_first20_prefixed "$path"
  else
    pass "$name"
  fi
}

assert_json_parseable() {
  local path="$1"
  local name="$2"

  if [[ -z "$JSON_PYTHON" ]]; then
    fail "$name (python not found for JSON parsing)"
    return
  fi

  if "$JSON_PYTHON" - "$path" <<'PY' >/dev/null 2>&1
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    json.load(f)
PY
  then
    pass "$name"
  else
    fail "$name (invalid JSON: $path)"
  fi
}

# Expression receives JSON object as variable `j`
assert_json_expr() {
  local path="$1"
  local name="$2"
  local expr="$3"

  if [[ -z "$JSON_PYTHON" ]]; then
    fail "$name (python not found for JSON predicate)"
    return
  fi

  if "$JSON_PYTHON" - "$path" "$expr" <<'PY' >/dev/null 2>&1
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    j = json.load(f)
expr = sys.argv[2]
ok = bool(eval(expr, {}, {"j": j}))
raise SystemExit(0 if ok else 1)
PY
  then
    pass "$name"
  else
    fail "$name (predicate false)"
  fi
}

assert_output_contains() {
  local needle="$1"
  local name="$2"
  local ci="${3:-0}"  # 1 => case-insensitive
  local combined="$TEMP_DIR/combined_output.txt"

  : >"$combined"
  [[ -f "$LAST_STDOUT" ]] && cat "$LAST_STDOUT" >>"$combined"
  printf '\n' >>"$combined"
  [[ -f "$LAST_STDERR" ]] && cat "$LAST_STDERR" >>"$combined"

  local ok=1
  if [[ "$ci" == "1" ]]; then
    if grep -Fqi -- "$needle" "$combined"; then ok=0; fi
  else
    if grep -Fq -- "$needle" "$combined"; then ok=0; fi
  fi

  if [[ $ok -eq 0 ]]; then
    pass "$name"
  else
    fail "$name (missing '$needle')"
    print_file_first20_prefixed "$combined"
  fi
}

# ------------------------------
# Exec helpers
# ------------------------------
resolve_executable_for_invocation() {
  local exe="$1"
  if [[ -z "${exe//[[:space:]]/}" ]]; then
    printf '%s\n' "$exe"
    return 0
  fi

  # Path-like? keep as-is
  if [[ "$exe" == */* ]]; then
    printf '%s\n' "$exe"
    return 0
  fi

  # PATH lookup
  if command -v -- "$exe" >/dev/null 2>&1; then
    command -v -- "$exe"
  else
    printf '%s\n' "$exe"
  fi
}

join_cmd_for_display() {
  local out=""
  local x
  for x in "$@"; do
    # shell-escaped view for readable diagnostics
    printf -v xq '%q' "$x"
    out+="$xq "
  done
  printf '%s\n' "${out% }"
}

invoke_native() {
  local exe="$1"; shift || true
  local -a args=( "$@" )

  # Reset capture files
  : >"$LAST_STDOUT"
  : >"$LAST_STDERR"

  local resolved_exe
  resolved_exe="$(resolve_executable_for_invocation "$exe")"

  # Existence check:
  # - path-like exe must exist
  # - non-path exe should have been resolved by command -v; if not, this will fail too
  if [[ "$resolved_exe" == */* ]]; then
    if [[ ! -e "$resolved_exe" ]]; then
      write_text_file "$LAST_STDERR" "Executable not found: $exe"
      LAST_RC=126
      LAST_CMD="$(join_cmd_for_display "$exe" "${args[@]}")"
      return 0
    fi
  else
    if ! command -v -- "$resolved_exe" >/dev/null 2>&1; then
      write_text_file "$LAST_STDERR" "Executable not found: $exe"
      LAST_RC=126
      LAST_CMD="$(join_cmd_for_display "$exe" "${args[@]}")"
      return 0
    fi
  fi

  LAST_CMD="$(join_cmd_for_display "$resolved_exe" "${args[@]}")"

  # Run command, capture stdout/stderr, preserve rc without aborting the harness
  local rc
  set +e
  "$resolved_exe" "${args[@]}" >"$LAST_STDOUT" 2>"$LAST_STDERR"
  rc=$?
  set -e 2>/dev/null || true  # harmless even if -e wasn't enabled
  set +e                      # keep harness non-terminating for expected failures
  LAST_RC=$rc

  return 0
}

contains_expected_rc() {
  local rc="$1"
  local expected_csv="$2"
  local IFS=','
  local code
  for code in $expected_csv; do
    code="${code//[[:space:]]/}"
    [[ -z "$code" ]] && continue
    if [[ "$rc" == "$code" ]]; then
      return 0
    fi
  done
  return 1
}

invoke_capture() {
  local name="$1"
  local expected_csv="$2"
  local exe="$3"; shift 3
  local -a args=( "$@" )

  invoke_native "$exe" "${args[@]}"

  if contains_expected_rc "$LAST_RC" "$expected_csv"; then
    pass "$name (rc=$LAST_RC)"
    return 0
  else
    fail "$name (rc=$LAST_RC; expected $expected_csv)"
    printf '  Command: %s\n' "$LAST_CMD"
    printf '  --- stdout (first 20 lines) ---\n'
    print_file_first20_prefixed "$LAST_STDOUT"
    printf '  --- stderr (first 20 lines) ---\n'
    print_file_first20_prefixed "$LAST_STDERR"
    return 1
  fi
}

have_verify_subcommand() {
  invoke_native "$RESOLVED_EXE_PATH" --help
  local combined="$TEMP_DIR/help_combined.txt"
  cat "$LAST_STDOUT" "$LAST_STDERR" >"$combined"
  if grep -Eq '(^|[[:space:]])verify([[:space:]]|$)' "$combined"; then
    return 0
  fi
  return 1
}

# ------------------------------
# Main
# ------------------------------
RESOLVED_EXE_PATH="$(resolve_path_safe "$EXE_PATH")"
RESOLVED_MODEL_PATH="$(resolve_path_safe "$MODEL_PATH")"
RESOLVED_VERIFY_FIXTURE_PATH="$(resolve_path_safe "$VERIFY_FIXTURE_PATH")"

hr
echo "pairwise-cli Linux Professor Check Suite"
echo "EXE      : $EXE_PATH"
echo "Model    : $MODEL_PATH"
echo "Temp dir : $TEMP_DIR"
hr
echo "Resolved EXE        : $RESOLVED_EXE_PATH"
echo "Resolved Model      : $RESOLVED_MODEL_PATH"
echo "Resolved VerifyCase : $RESOLVED_VERIFY_FIXTURE_PATH"

# 0) Preconditions
assert_file_exists "$RESOLVED_EXE_PATH" "Linux EXE exists"
assert_file_non_empty "$RESOLVED_EXE_PATH" "Linux EXE is non-empty"
assert_file_exists "$RESOLVED_MODEL_PATH" "Sample model exists"

if [[ ! -e "$RESOLVED_EXE_PATH" || ! -e "$RESOLVED_MODEL_PATH" ]]; then
  fail "PreflightFailed: missing EXE or sample model"
  hr
  echo "SUMMARY"
  echo "  PASS: $PASS_COUNT"
  echo "  FAIL: $FAIL_COUNT"
  echo "  SKIP: $SKIP_COUNT"
  hr
  echo "Overall: FAIL"
  exit 1
fi

# 1) Help surfaces / contract presence
invoke_capture "Root --help" "0" "$RESOLVED_EXE_PATH" --help
assert_output_contains "generate" "Root help lists generate"
assert_output_contains "doctor" "Root help lists doctor"

invoke_capture "generate --help" "0" "$RESOLVED_EXE_PATH" generate --help
assert_output_contains "--verify" "generate help shows --verify"
assert_output_contains "--no-verify" "generate help shows --no-verify"
assert_output_contains "--early-stop" "generate help shows --early-stop"
assert_output_contains "--no-early-stop" "generate help shows --no-early-stop"
assert_output_contains "--total-timeout-sec" "generate help shows --total-timeout-sec"
assert_output_contains "--max-tries" "generate help shows --max-tries"

HAS_VERIFY=0
if have_verify_subcommand; then
  HAS_VERIFY=1
  invoke_capture "verify --help" "0" "$RESOLVED_EXE_PATH" verify --help
else
  skip "verify subcommand help (subcommand not present)"
fi

# 2) doctor
invoke_capture "doctor" "0" "$RESOLVED_EXE_PATH" doctor
assert_contains "$LAST_STDOUT" "PICT Execution" "doctor output contains PICT Execution"
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "doctor stderr has no traceback"

# 3) Verified generation (auto-order, deterministic)
OUT_JSON="$TEMP_DIR/out_verified.json"
invoke_capture "generate verified auto deterministic json" "0" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --format json \
  --verify --early-stop --ordering auto \
  --tries 200 --seed 0 --deterministic
cp -f "$LAST_STDOUT" "$OUT_JSON"
assert_file_non_empty "$OUT_JSON" "Verified JSON output captured"
assert_json_parseable "$OUT_JSON" "Verified JSON parses"
assert_json_expr "$OUT_JSON" "Verified JSON top-level keys" '("metadata" in j) and ("test_cases" in j)'
assert_json_expr "$OUT_JSON" "metadata.verified == true" 'j["metadata"]["verified"] is True'
assert_json_expr "$OUT_JSON" "metadata.ordering_mode == auto" 'str(j["metadata"]["ordering_mode"]) == "auto"'
assert_json_expr "$OUT_JSON" "metadata.lb == 16" 'int(j["metadata"]["lb"]) == 16'
assert_json_expr "$OUT_JSON" "metadata.n >= 16" 'int(j["metadata"]["n"]) >= 16'
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "Verified generation stderr has no traceback"

# 4) No-verify truthfulness
OUT_NOVERIFY="$TEMP_DIR/out_noverify.json"
invoke_capture "generate no-verify json" "0" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --format json --no-verify
cp -f "$LAST_STDOUT" "$OUT_NOVERIFY"
assert_json_parseable "$OUT_NOVERIFY" "No-verify JSON parses"
assert_json_expr "$OUT_NOVERIFY" "metadata.verified == false under --no-verify" 'j["metadata"]["verified"] is False'
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "No-verify stderr has no traceback"

# 5) JSON purity under verbose logging
OUT_VERBOSE="$TEMP_DIR/out_verbose.json"
ERR_VERBOSE="$TEMP_DIR/out_verbose.err"
invoke_capture "generate json verbose purity" "0" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --format json --verbose
cp -f "$LAST_STDOUT" "$OUT_VERBOSE"
cp -f "$LAST_STDERR" "$ERR_VERBOSE"
assert_json_parseable "$OUT_VERBOSE" "Verbose stdout still valid JSON"
assert_file_non_empty "$ERR_VERBOSE" "Verbose logs go to stderr (non-empty stderr)"
assert_not_contains "$ERR_VERBOSE" "Traceback (most recent call last)" "Verbose stderr has no traceback"

# 6) Determinism
DET1="$TEMP_DIR/det1.json"
DET2="$TEMP_DIR/det2.json"

invoke_capture "determinism run #1" "0" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --format json \
  --verify --early-stop --ordering auto \
  --tries 200 --seed 123 --deterministic
cp -f "$LAST_STDOUT" "$DET1"

invoke_capture "determinism run #2" "0" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --format json \
  --verify --early-stop --ordering auto \
  --tries 200 --seed 123 --deterministic
cp -f "$LAST_STDOUT" "$DET2"

if command -v sha256sum >/dev/null 2>&1; then
  H1="$(sha256sum "$DET1" | awk '{print $1}')"
  H2="$(sha256sum "$DET2" | awk '{print $1}')"
else
  H1="$(cksum "$DET1" | awk '{print $1 ":" $2}')"
  H2="$(cksum "$DET2" | awk '{print $1 ":" $2}')"
fi

if [[ "$H1" == "$H2" ]]; then
  pass "Determinism: identical JSON for same seed/flags"
else
  fail "Determinism: outputs differ"
fi

# 7) Ordering modes
KEEP_JSON="$TEMP_DIR/keep.json"
invoke_capture "generate ordering=keep" "0" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --format json \
  --verify --early-stop --ordering keep \
  --tries 50 --seed 0 --deterministic
cp -f "$LAST_STDOUT" "$KEEP_JSON"
assert_json_parseable "$KEEP_JSON" "Ordering keep JSON parses"
assert_json_expr "$KEEP_JSON" "metadata.ordering_mode == keep" 'str(j["metadata"]["ordering_mode"]) == "keep"'

KEEP_ALIAS_JSON="$TEMP_DIR/keep_alias.json"
invoke_capture "generate --keep-order alias" "0" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --format json \
  --verify --early-stop --keep-order \
  --tries 50 --seed 0 --deterministic
cp -f "$LAST_STDOUT" "$KEEP_ALIAS_JSON"
assert_json_parseable "$KEEP_ALIAS_JSON" "keep-order alias JSON parses"
assert_json_expr "$KEEP_ALIAS_JSON" "keep-order alias yields keep ordering metadata" 'str(j["metadata"]["ordering_mode"]) == "keep"'

# 8) CSV generation + verify success (if verify exists)
CSV_OUT="$TEMP_DIR/generated_cases.csv"
invoke_capture "generate csv to file" "0" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --format csv \
  --out "$CSV_OUT" --verify --early-stop --ordering auto \
  --tries 100 --seed 0 --deterministic
assert_file_non_empty "$CSV_OUT" "CSV file generated"

FIRST_LINE=""
if [[ -f "$CSV_OUT" ]]; then
  FIRST_LINE="$(head -n 1 "$CSV_OUT" 2>/dev/null || true)"
fi
if [[ "$FIRST_LINE" == *","* ]]; then
  pass "Generated CSV header appears CSV-like"
else
  fail "Generated CSV header not CSV-like"
fi

if [[ $HAS_VERIFY -eq 1 ]]; then
  invoke_capture "verify generated CSV succeeds" "0" "$RESOLVED_EXE_PATH" \
    verify --model "$RESOLVED_MODEL_PATH" --cases "$CSV_OUT"
  assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "verify success stderr has no traceback"
else
  skip "verify generated CSV succeeds (verify subcommand not present)"
fi

# 9) Validation error paths (exit 2)
invoke_capture "validation: strength < 2 => exit 2" "2" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --strength 1
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "strength validation has no traceback"

invoke_capture "validation: tries=0 => exit 2" "2" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --tries 0
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "tries=0 validation has no traceback"

invoke_capture "validation: tries > max-tries => exit 2" "2" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --tries 999999 --max-tries 10
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "tries bound validation has no traceback"

invoke_capture "validation: pict-timeout-sec <= 0 => exit 2" "2" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --pict-timeout-sec 0
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "pict-timeout validation has no traceback"

invoke_capture "validation: total-timeout-sec <= 0 => exit 2" "2" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --total-timeout-sec 0
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "total-timeout validation has no traceback"

# 10) Warning path: total timeout < pict-timeout (may still succeed or timeout)
WARN_OUT="$TEMP_DIR/warn.json"
WARN_ERR="$TEMP_DIR/warn.err"
invoke_capture "warning path total-timeout < pict-timeout" "0,5" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --format json \
  --tries 1 --pict-timeout-sec 10 --total-timeout-sec 0.5
cp -f "$LAST_STDOUT" "$WARN_OUT"
cp -f "$LAST_STDERR" "$WARN_ERR"
assert_contains "$WARN_ERR" "warning" "Warning emitted when total-timeout < pict-timeout" 1
if [[ "$LAST_RC" -eq 0 ]]; then
  assert_json_parseable "$WARN_OUT" "Warning path stdout valid JSON when generation succeeds"
fi
assert_not_contains "$WARN_ERR" "Traceback (most recent call last)" "Warning path stderr has no traceback"

# 11) Timeout paths (exit 5)
PER_PICT_TIMEOUT_OBSERVED=0
for tv in 0.0005 0.0001; do
  invoke_capture "timeout: per-PICT timeout $tv" "5" "$RESOLVED_EXE_PATH" \
    generate --model "$RESOLVED_MODEL_PATH" \
    --pict-timeout-sec "$tv" --tries 50 --format json --no-early-stop
  if [[ "$LAST_RC" -eq 5 ]]; then
    PER_PICT_TIMEOUT_OBSERVED=1
    break
  fi
done
if [[ $PER_PICT_TIMEOUT_OBSERVED -eq 1 ]]; then
  pass "per-PICT adaptive timeout observed exit 5"
else
  fail "per-PICT adaptive timeout did not exit 5 (last rc=$LAST_RC)"
fi
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "per-PICT timeout path has no traceback"

invoke_capture "timeout: tiny total timeout => exit 5" "5" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --total-timeout-sec 0.01 --tries 500 --format json
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "total timeout path has no traceback"

# 12) Verify failure path (exit 4) on incomplete fixture
if [[ $HAS_VERIFY -eq 1 && -e "$RESOLVED_VERIFY_FIXTURE_PATH" ]]; then
  invoke_capture "verify incomplete fixture => exit 4" "4" "$RESOLVED_EXE_PATH" \
    verify --model "$RESOLVED_MODEL_PATH" --cases "$RESOLVED_VERIFY_FIXTURE_PATH"
  assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "verify failure path has no traceback"

  COMBINED="$TEMP_DIR/verify_fail_combined.txt"
  cat "$LAST_STDOUT" "$LAST_STDERR" >"$COMBINED"

  FOUND_DIAG=0
  for pat in "missing pair" "missing pairs" "coverage verification failed" "missing"; do
    if grep -Eqi -- "$pat" "$COMBINED"; then
      FOUND_DIAG=1
      break
    fi
  done

  if [[ $FOUND_DIAG -eq 1 ]]; then
    pass "Verify failure reports missing pairs/details"
  else
    fail "Verify failure missing-pair diagnostics not found"
  fi
else
  skip "verify incomplete fixture => exit 4 (verify subcommand or fixture missing)"
fi

# 13) Strength != 2 semantics (lb should be null)
S3_OUT="$TEMP_DIR/strength3.json"
invoke_capture "strength=3 JSON generation" "0" "$RESOLVED_EXE_PATH" \
  generate --model "$RESOLVED_MODEL_PATH" --strength 3 --format json --no-verify
cp -f "$LAST_STDOUT" "$S3_OUT"
assert_json_parseable "$S3_OUT" "Strength=3 JSON parses"
assert_json_expr "$S3_OUT" "Strength=3 metadata.lb is null" 'j["metadata"]["lb"] is None'

# 14) Missing/malformed/non-UTF8 model handling (no traceback)
MISSING_MODEL="$TEMP_DIR/does_not_exist.pict"
invoke_capture "missing model path handled" "2,3" "$RESOLVED_EXE_PATH" \
  generate --model "$MISSING_MODEL" --format json
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "Missing model path has no traceback"

BAD_MODEL="$TEMP_DIR/bad_model.pict"
{
  printf '%s\n' "This is not a valid PICT model"
  printf '%s\n' "No colon here maybe"
} >"$BAD_MODEL"
invoke_capture "malformed model file handled" "2,3" "$RESOLVED_EXE_PATH" \
  generate --model "$BAD_MODEL" --format json
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "Malformed model file has no traceback"

BAD_UTF8="$TEMP_DIR/bad_utf8_model.pict"
# bytes: FF FE FA FB
printf '\xFF\xFE\xFA\xFB' >"$BAD_UTF8"
invoke_capture "non-UTF8 model file handled" "2,3" "$RESOLVED_EXE_PATH" \
  generate --model "$BAD_UTF8" --format json
assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "Non-UTF8 model file has no traceback"

# 15) Malformed verify inputs (if verify exists)
if [[ $HAS_VERIFY -eq 1 ]]; then
  EMPTY_CSV="$TEMP_DIR/empty_cases.csv"
  : >"$EMPTY_CSV"
  invoke_capture "verify empty CSV handled" "2,3,4" "$RESOLVED_EXE_PATH" \
    verify --model "$RESOLVED_MODEL_PATH" --cases "$EMPTY_CSV"
  assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "verify empty CSV has no traceback"

  BAD_CASES_JSON="$TEMP_DIR/bad_cases.json"
  printf '%s\n' "{ this is not json }" >"$BAD_CASES_JSON"
  invoke_capture "verify malformed JSON handled" "2,3,4" "$RESOLVED_EXE_PATH" \
    verify --model "$RESOLVED_MODEL_PATH" --cases "$BAD_CASES_JSON"
  assert_not_contains "$LAST_STDERR" "Traceback (most recent call last)" "verify malformed JSON has no traceback"
else
  skip "Malformed verify input checks (verify subcommand not present)"
fi

# 16) Optional pytest / acceptance evidence (skip if unavailable)
HAS_PY=0
PY_CMD=""
if command -v python3 >/dev/null 2>&1; then
  PY_CMD="$(command -v python3)"
  HAS_PY=1
elif command -v python >/dev/null 2>&1; then
  PY_CMD="$(command -v python)"
  HAS_PY=1
fi

ACCEPTANCE_RUNNER_PATH="$(resolve_path_safe "./acceptance/run_acceptance.py")"

if [[ $HAS_PY -eq 1 && -e "$ACCEPTANCE_RUNNER_PATH" ]]; then
  invoke_native "$PY_CMD" -m pytest --version
  if [[ "$LAST_RC" -eq 0 ]]; then
    invoke_capture "pytest acceptance marker (optional)" "0" "$PY_CMD" \
      -m pytest -m acceptance -q

    invoke_capture "acceptance runner exe mode (optional)" "0" "$PY_CMD" \
      acceptance/run_acceptance.py --mode exe --timeout-sec 60
  else
    skip "Optional pytest/acceptance checks (pytest not installed)"
  fi
else
  skip "Optional pytest/acceptance checks (python or acceptance script missing)"
fi

# 17) Optional default invocation EOF smoke (best effort)
# Use direct stdin redirection from /dev/null to simulate immediate EOF.
EOF_OUT="$TEMP_DIR/eof_out.txt"
EOF_ERR="$TEMP_DIR/eof_err.txt"
: >"$EOF_OUT"
: >"$EOF_ERR"

set +e
"$RESOLVED_EXE_PATH" </dev/null >"$EOF_OUT" 2>"$EOF_ERR"
EOF_RC=$?
set -e 2>/dev/null || true
set +e

if contains_expected_rc "$EOF_RC" "0,1,2,3,4,5"; then
  pass "Default invocation EOF smoke (rc=$EOF_RC)"
else
  fail "Default invocation EOF smoke (rc=$EOF_RC; expected 0,1,2,3,4,5)"
  printf '  Command: %q < /dev/null > %q 2> %q\n' "$RESOLVED_EXE_PATH" "$EOF_OUT" "$EOF_ERR"
  printf '  --- stdout (first 20 lines) ---\n'
  print_file_first20_prefixed "$EOF_OUT"
  printf '  --- stderr (first 20 lines) ---\n'
  print_file_first20_prefixed "$EOF_ERR"
fi

assert_file_exists "$EOF_OUT" "EOF smoke stdout file exists"
assert_file_exists "$EOF_ERR" "EOF smoke stderr file exists"
assert_not_contains "$EOF_ERR" "Traceback (most recent call last)" "EOF smoke stderr has no traceback"

# ------------------------------
# Summary / exit
# ------------------------------
hr
echo "SUMMARY"
echo "  PASS: $PASS_COUNT"
echo "  FAIL: $FAIL_COUNT"
echo "  SKIP: $SKIP_COUNT"
hr

if [[ "$FAIL_COUNT" -eq 0 ]]; then
  echo -e "\033[32mOverall: PASS\033[0m"
  exit 0
else
  echo -e "\033[31mOverall: FAIL\033[0m"
  exit 1
fi