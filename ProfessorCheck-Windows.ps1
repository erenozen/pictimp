# pairwise-cli professor-style automated check suite (Windows PowerShell)
[CmdletBinding()]
param(
    [string]$ExePath = ".\dist\pairwise-cli-win-x64.exe",
    [string]$ModelPath = ".\examples\sample.pict",
    [string]$VerifyFixturePath = ".\acceptance\fixtures\incomplete_cases.csv"
)

$ErrorActionPreference = "Stop"

$script:PassCount = 0
$script:FailCount = 0
$script:SkipCount = 0

$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("pairwise-profcheck-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $TempDir | Out-Null

$script:LastStdout = Join-Path $TempDir "last_stdout.txt"
$script:LastStderr = Join-Path $TempDir "last_stderr.txt"
$script:LastRc = -999

function HR { "------------------------------------------------------------" | Write-Host }
function Pass([string]$Name) { $script:PassCount++; Write-Host "PASS: $Name" -ForegroundColor Green }
function Fail([string]$Name) { $script:FailCount++; Write-Host "FAIL: $Name" -ForegroundColor Red }
function Skip([string]$Name) { $script:SkipCount++; Write-Host "SKIP: $Name" -ForegroundColor Yellow }

function Assert-FileExists([string]$Path, [string]$Name) {
    if (Test-Path -LiteralPath $Path) { Pass $Name } else { Fail "$Name (missing: $Path)" }
}
function Assert-FileNonEmpty([string]$Path, [string]$Name) {
    if ((Test-Path -LiteralPath $Path) -and ((Get-Item -LiteralPath $Path).Length -gt 0)) {
        Pass $Name
    } else {
        Fail "$Name (empty/missing: $Path)"
    }
}
function Assert-Contains([string]$Path, [string]$Needle, [string]$Name, [switch]$CaseInsensitive) {
    if (-not (Test-Path -LiteralPath $Path)) { Fail "$Name (file missing: $Path)"; return }
    $content = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
    if ($null -eq $content) { $content = "" }
    $ok = if ($CaseInsensitive) { $content.ToLower().Contains($Needle.ToLower()) } else { $content.Contains($Needle) }
    if ($ok) { Pass $Name } else {
        Fail "$Name (missing '$Needle')"
        ($content -split "`r?`n" | Select-Object -First 20 | ForEach-Object { "    $_" }) | Write-Host
    }
}
function Assert-NotContains([string]$Path, [string]$Needle, [string]$Name) {
    if (-not (Test-Path -LiteralPath $Path)) { Pass $Name; return }
    $content = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
    if ($null -eq $content) { $content = "" }
    if ($content.Contains($Needle)) {
        Fail "$Name (found forbidden '$Needle')"
        ($content -split "`r?`n" | Select-Object -First 20 | ForEach-Object { "    $_" }) | Write-Host
    } else {
        Pass $Name
    }
}
function Assert-JsonParseable([string]$Path, [string]$Name) {
    try {
        Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json | Out-Null
        Pass $Name
    } catch {
        Fail "$Name (invalid JSON: $Path)"
    }
}
function Assert-JsonPredicate([string]$Path, [string]$Name, [scriptblock]$Predicate) {
    try {
        $obj = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        $ok = & $Predicate $obj
        if ($ok) { Pass $Name } else { Fail "$Name (predicate false)" }
    } catch {
        Fail "$Name (JSON read/predicate error: $($_.Exception.Message))"
    }
}

function Invoke-Capture {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][int[]]$ExpectedExitCodes,
        [Parameter(Mandatory=$true)][scriptblock]$Command
    )

    "" | Set-Content -LiteralPath $script:LastStdout -NoNewline
    "" | Set-Content -LiteralPath $script:LastStderr -NoNewline

    try {
        & $Command 1> $script:LastStdout 2> $script:LastStderr
        $script:LastRc = $LASTEXITCODE
        if ($null -eq $script:LastRc) { $script:LastRc = 0 }
    } catch {
        # PowerShell-level failure (should be rare for native command invocations)
        $script:LastRc = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { 999 }
        Add-Content -LiteralPath $script:LastStderr -Value $_.Exception.Message
    }

    if ($ExpectedExitCodes -contains [int]$script:LastRc) {
        Pass "$Name (rc=$script:LastRc)"
        return $true
    } else {
        Fail "$Name (rc=$script:LastRc; expected $($ExpectedExitCodes -join ','))"
        Write-Host "  --- stdout (first 20 lines) ---"
        Get-Content -LiteralPath $script:LastStdout -ErrorAction SilentlyContinue | Select-Object -First 20 | ForEach-Object { Write-Host "    $_" }
        Write-Host "  --- stderr (first 20 lines) ---"
        Get-Content -LiteralPath $script:LastStderr -ErrorAction SilentlyContinue | Select-Object -First 20 | ForEach-Object { Write-Host "    $_" }
        return $false
    }
}

function Have-VerifySubcommand {
    try {
        $txt = & $ExePath --help 2>$null | Out-String
        return ($txt -match '(^|\s)verify(\s|$)')
    } catch {
        return $false
    }
}

HR
Write-Host "pairwise-cli Windows Professor Check Suite"
Write-Host "EXE      : $ExePath"
Write-Host "Model    : $ModelPath"
Write-Host "Temp dir : $TempDir"
HR

try {
    # 0) Preconditions
    Assert-FileExists $ExePath "Windows EXE exists"
    Assert-FileNonEmpty $ExePath "Windows EXE is non-empty"
    Assert-FileExists $ModelPath "Sample model exists"

    # 1) Help surfaces / contract presence
    Invoke-Capture -Name "Root --help" -ExpectedExitCodes @(0) -Command { & $ExePath --help } | Out-Null
    Assert-Contains $script:LastStdout "generate" "Root help lists generate"
    Assert-Contains $script:LastStdout "doctor" "Root help lists doctor"

    Invoke-Capture -Name "generate --help" -ExpectedExitCodes @(0) -Command { & $ExePath generate --help } | Out-Null
    Assert-Contains $script:LastStdout "--verify" "generate help shows --verify"
    Assert-Contains $script:LastStdout "--no-verify" "generate help shows --no-verify"
    Assert-Contains $script:LastStdout "--early-stop" "generate help shows --early-stop"
    Assert-Contains $script:LastStdout "--no-early-stop" "generate help shows --no-early-stop"
    Assert-Contains $script:LastStdout "--total-timeout-sec" "generate help shows --total-timeout-sec"
    Assert-Contains $script:LastStdout "--max-tries" "generate help shows --max-tries"

    $hasVerify = Have-VerifySubcommand
    if ($hasVerify) {
        Invoke-Capture -Name "verify --help" -ExpectedExitCodes @(0) -Command { & $ExePath verify --help } | Out-Null
    } else {
        Skip "verify subcommand help (subcommand not present)"
    }

    # 2) doctor
    Invoke-Capture -Name "doctor" -ExpectedExitCodes @(0) -Command { & $ExePath doctor } | Out-Null
    Assert-Contains $script:LastStdout "PICT Execution" "doctor output contains PICT Execution"
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "doctor stderr has no traceback"

    # 3) Verified generation (auto-order, deterministic)
    $OutJson = Join-Path $TempDir "out_verified.json"
    Invoke-Capture -Name "generate verified auto deterministic json" -ExpectedExitCodes @(0) -Command {
        & $ExePath generate --model $ModelPath --format json --verify --early-stop --ordering auto --tries 200 --seed 0 --deterministic
    } | Out-Null
    Copy-Item $script:LastStdout $OutJson -Force
    Assert-FileNonEmpty $OutJson "Verified JSON output captured"
    Assert-JsonParseable $OutJson "Verified JSON parses"
    Assert-JsonPredicate $OutJson "Verified JSON top-level keys" { param($j) ($j.PSObject.Properties.Name -contains 'metadata') -and ($j.PSObject.Properties.Name -contains 'test_cases') }
    Assert-JsonPredicate $OutJson "metadata.verified == true" { param($j) $j.metadata.verified -eq $true }
    Assert-JsonPredicate $OutJson "metadata.ordering_mode == auto" { param($j) [string]$j.metadata.ordering_mode -eq 'auto' }
    Assert-JsonPredicate $OutJson "metadata.lb == 16" { param($j) [int]$j.metadata.lb -eq 16 }
    Assert-JsonPredicate $OutJson "metadata.n >= 16" { param($j) [int]$j.metadata.n -ge 16 }
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "Verified generation stderr has no traceback"

    # 4) No-verify truthfulness
    $OutNoVerify = Join-Path $TempDir "out_noverify.json"
    Invoke-Capture -Name "generate no-verify json" -ExpectedExitCodes @(0) -Command {
        & $ExePath generate --model $ModelPath --format json --no-verify
    } | Out-Null
    Copy-Item $script:LastStdout $OutNoVerify -Force
    Assert-JsonParseable $OutNoVerify "No-verify JSON parses"
    Assert-JsonPredicate $OutNoVerify "metadata.verified == false under --no-verify" { param($j) $j.metadata.verified -eq $false }
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "No-verify stderr has no traceback"

    # 5) JSON purity under verbose logging
    $OutVerbose = Join-Path $TempDir "out_verbose.json"
    $ErrVerbose = Join-Path $TempDir "out_verbose.err"
    try {
        & $ExePath generate --model $ModelPath --format json --verbose 1> $OutVerbose 2> $ErrVerbose
        $script:LastRc = $LASTEXITCODE
    } catch {
        $script:LastRc = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { 999 }
        $_.Exception.Message | Out-File -FilePath $ErrVerbose -Append -Encoding utf8
    }
    if ($script:LastRc -eq 0) { Pass "generate json verbose purity (rc=0)" } else { Fail "generate json verbose purity (rc=$script:LastRc expected 0)" }
    Assert-JsonParseable $OutVerbose "Verbose stdout still valid JSON"
    Assert-FileNonEmpty $ErrVerbose "Verbose logs go to stderr (non-empty stderr)"
    Assert-NotContains $ErrVerbose "Traceback (most recent call last)" "Verbose stderr has no traceback"

    # 6) Determinism
    $Det1 = Join-Path $TempDir "det1.json"
    $Det2 = Join-Path $TempDir "det2.json"
    Invoke-Capture -Name "determinism run #1" -ExpectedExitCodes @(0) -Command {
        & $ExePath generate --model $ModelPath --format json --verify --early-stop --ordering auto --tries 200 --seed 123 --deterministic
    } | Out-Null
    Copy-Item $script:LastStdout $Det1 -Force
    Invoke-Capture -Name "determinism run #2" -ExpectedExitCodes @(0) -Command {
        & $ExePath generate --model $ModelPath --format json --verify --early-stop --ordering auto --tries 200 --seed 123 --deterministic
    } | Out-Null
    Copy-Item $script:LastStdout $Det2 -Force
    if ((Get-FileHash $Det1).Hash -eq (Get-FileHash $Det2).Hash) { Pass "Determinism: identical JSON for same seed/flags" } else { Fail "Determinism: outputs differ" }

    # 7) Ordering modes
    $KeepJson = Join-Path $TempDir "keep.json"
    Invoke-Capture -Name "generate ordering=keep" -ExpectedExitCodes @(0) -Command {
        & $ExePath generate --model $ModelPath --format json --verify --early-stop --ordering keep --tries 50 --seed 0 --deterministic
    } | Out-Null
    Copy-Item $script:LastStdout $KeepJson -Force
    Assert-JsonParseable $KeepJson "Ordering keep JSON parses"
    Assert-JsonPredicate $KeepJson "metadata.ordering_mode == keep" { param($j) [string]$j.metadata.ordering_mode -eq 'keep' }

    $KeepAliasJson = Join-Path $TempDir "keep_alias.json"
    Invoke-Capture -Name "generate --keep-order alias" -ExpectedExitCodes @(0) -Command {
        & $ExePath generate --model $ModelPath --format json --verify --early-stop --keep-order --tries 50 --seed 0 --deterministic
    } | Out-Null
    Copy-Item $script:LastStdout $KeepAliasJson -Force
    Assert-JsonParseable $KeepAliasJson "keep-order alias JSON parses"
    Assert-JsonPredicate $KeepAliasJson "keep-order alias yields keep ordering metadata" { param($j) [string]$j.metadata.ordering_mode -eq 'keep' }

    # 8) CSV generation + verify success (if verify exists)
    $CsvOut = Join-Path $TempDir "generated_cases.csv"
    Invoke-Capture -Name "generate csv to file" -ExpectedExitCodes @(0) -Command {
        & $ExePath generate --model $ModelPath --format csv --out $CsvOut --verify --early-stop --ordering auto --tries 100 --seed 0 --deterministic
    } | Out-Null
    Assert-FileNonEmpty $CsvOut "CSV file generated"
    $firstLine = Get-Content -LiteralPath $CsvOut -TotalCount 1
    if ($firstLine -match ',') { Pass "Generated CSV header appears CSV-like" } else { Fail "Generated CSV header not CSV-like" }

    if ($hasVerify) {
        Invoke-Capture -Name "verify generated CSV succeeds" -ExpectedExitCodes @(0) -Command {
            & $ExePath verify --model $ModelPath --cases $CsvOut
        } | Out-Null
        Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "verify success stderr has no traceback"
    } else {
        Skip "verify generated CSV succeeds (verify subcommand not present)"
    }

    # 9) Validation error paths (exit 2)
    Invoke-Capture -Name "validation: strength < 2 => exit 2" -ExpectedExitCodes @(2) -Command {
        & $ExePath generate --model $ModelPath --strength 1
    } | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "strength validation has no traceback"

    Invoke-Capture -Name "validation: tries=0 => exit 2" -ExpectedExitCodes @(2) -Command {
        & $ExePath generate --model $ModelPath --tries 0
    } | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "tries=0 validation has no traceback"

    Invoke-Capture -Name "validation: tries > max-tries => exit 2" -ExpectedExitCodes @(2) -Command {
        & $ExePath generate --model $ModelPath --tries 999999 --max-tries 10
    } | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "tries bound validation has no traceback"

    Invoke-Capture -Name "validation: pict-timeout-sec <= 0 => exit 2" -ExpectedExitCodes @(2) -Command {
        & $ExePath generate --model $ModelPath --pict-timeout-sec 0
    } | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "pict-timeout validation has no traceback"

    Invoke-Capture -Name "validation: total-timeout-sec <= 0 => exit 2" -ExpectedExitCodes @(2) -Command {
        & $ExePath generate --model $ModelPath --total-timeout-sec 0
    } | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "total-timeout validation has no traceback"

    # 10) Warning path: total timeout < per-try timeout
    $WarnOut = Join-Path $TempDir "warn.json"
    $WarnErr = Join-Path $TempDir "warn.err"
    try {
        & $ExePath generate --model $ModelPath --format json --tries 1 --pict-timeout-sec 10 --total-timeout-sec 0.5 1> $WarnOut 2> $WarnErr
        $script:LastRc = $LASTEXITCODE
    } catch {
        $script:LastRc = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { 999 }
        $_.Exception.Message | Out-File -FilePath $WarnErr -Append -Encoding utf8
    }
    if (@(0,5) -contains [int]$script:LastRc) { Pass "warning path total-timeout < pict-timeout (rc=$script:LastRc)" } else { Fail "warning path total-timeout < pict-timeout (rc=$script:LastRc expected 0 or 5)" }
    Assert-Contains $WarnErr "warning" "Warning emitted when total-timeout < pict-timeout" -CaseInsensitive
    if ($script:LastRc -eq 0) { Assert-JsonParseable $WarnOut "Warning path stdout valid JSON when generation succeeds" }
    Assert-NotContains $WarnErr "Traceback (most recent call last)" "Warning path stderr has no traceback"

    # 11) Timeout error paths (exit 5)
    Invoke-Capture -Name "timeout: tiny per-PICT timeout => exit 5" -ExpectedExitCodes @(5) -Command {
        & $ExePath generate --model $ModelPath --pict-timeout-sec 0.001 --tries 50 --format json
    } | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "per-PICT timeout path has no traceback"

    Invoke-Capture -Name "timeout: tiny total timeout => exit 5" -ExpectedExitCodes @(5) -Command {
        & $ExePath generate --model $ModelPath --total-timeout-sec 0.01 --tries 500 --format json
    } | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "total timeout path has no traceback"

    # 12) Verification failure path (exit 4)
    if ($hasVerify -and (Test-Path -LiteralPath $VerifyFixturePath)) {
        Invoke-Capture -Name "verify incomplete fixture => exit 4" -ExpectedExitCodes @(4) -Command {
            & $ExePath verify --model $ModelPath --cases $VerifyFixturePath
        } | Out-Null
        Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "verify failure path has no traceback"
        $combined = ((Get-Content -LiteralPath $script:LastStdout -Raw -ErrorAction SilentlyContinue) + "`n" + (Get-Content -LiteralPath $script:LastStderr -Raw -ErrorAction SilentlyContinue))
        if ($combined -match '(?i)missing') { Pass "Verify failure reports missing pairs/details" } else { Fail "Verify failure missing-pair diagnostics not found" }
    } else {
        Skip "verify incomplete fixture => exit 4 (verify subcommand or fixture missing)"
    }

    # 13) Strength != 2 semantics (lb == null)
    $S3Out = Join-Path $TempDir "strength3.json"
    Invoke-Capture -Name "strength=3 JSON generation" -ExpectedExitCodes @(0) -Command {
        & $ExePath generate --model $ModelPath --strength 3 --format json --no-verify
    } | Out-Null
    Copy-Item $script:LastStdout $S3Out -Force
    Assert-JsonParseable $S3Out "Strength=3 JSON parses"
    Assert-JsonPredicate $S3Out "Strength=3 metadata.lb is null" { param($j) $null -eq $j.metadata.lb }

    # 14) Missing/malformed model handling (no traceback)
    $MissingModel = Join-Path $TempDir "does_not_exist.pict"
    Invoke-Capture -Name "missing model path handled" -ExpectedExitCodes @(2,3) -Command {
        & $ExePath generate --model $MissingModel --format json
    } | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "Missing model path has no traceback"

    $BadModel = Join-Path $TempDir "bad_model.pict"
    @"
This is not a valid PICT model
No colon here maybe
"@ | Set-Content -LiteralPath $BadModel -Encoding utf8
    Invoke-Capture -Name "malformed model file handled" -ExpectedExitCodes @(2,3) -Command {
        & $ExePath generate --model $BadModel --format json
    } | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "Malformed model file has no traceback"

    $BadUtf8 = Join-Path $TempDir "bad_utf8_model.pict"
    [System.IO.File]::WriteAllBytes($BadUtf8, [byte[]](0xFF,0xFE,0xFA,0xFB))
    Invoke-Capture -Name "non-UTF8 model file handled" -ExpectedExitCodes @(2,3) -Command {
        & $ExePath generate --model $BadUtf8 --format json
    } | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "Non-UTF8 model file has no traceback"

    # 15) Malformed verify input handling (if verify exists)
    if ($hasVerify) {
        $EmptyCsv = Join-Path $TempDir "empty_cases.csv"
        New-Item -ItemType File -Path $EmptyCsv -Force | Out-Null
        Invoke-Capture -Name "verify empty CSV handled" -ExpectedExitCodes @(2,3,4) -Command {
            & $ExePath verify --model $ModelPath --cases $EmptyCsv
        } | Out-Null
        Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "verify empty CSV has no traceback"

        $BadCasesJson = Join-Path $TempDir "bad_cases.json"
        "{ this is not json }" | Set-Content -LiteralPath $BadCasesJson -Encoding utf8
        Invoke-Capture -Name "verify malformed JSON handled" -ExpectedExitCodes @(2,3,4) -Command {
            & $ExePath verify --model $ModelPath --cases $BadCasesJson
        } | Out-Null
        Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "verify malformed JSON has no traceback"
    } else {
        Skip "Malformed verify input checks (verify subcommand not present)"
    }

    # 16) Optional acceptance evidence (if pytest + acceptance runner exist)
    $hasPython = $false
    $PythonCmd = $null
    foreach ($cand in @("py", "python")) {
        try {
            if ($cand -eq "py") {
                & py -3.11 -c "print('ok')" *> $null
                if ($LASTEXITCODE -eq 0) { $PythonCmd = "py -3.11"; $hasPython = $true; break }
            } else {
                & python -c "print('ok')" *> $null
                if ($LASTEXITCODE -eq 0) { $PythonCmd = "python"; $hasPython = $true; break }
            }
        } catch {}
    }

    if ($hasPython -and (Test-Path ".\acceptance\run_acceptance.py")) {
        # pytest marker (optional)
        try {
            & cmd.exe /c "$PythonCmd -m pytest --version" 1> $null 2> $null
            if ($LASTEXITCODE -eq 0) {
                Invoke-Capture -Name "pytest acceptance marker (optional)" -ExpectedExitCodes @(0) -Command {
                    & cmd.exe /c "$PythonCmd -m pytest -m acceptance -q"
                } | Out-Null

                Invoke-Capture -Name "acceptance runner exe mode (optional)" -ExpectedExitCodes @(0) -Command {
                    & cmd.exe /c "$PythonCmd acceptance/run_acceptance.py --mode exe --timeout-sec 60"
                } | Out-Null
            } else {
                Skip "Optional pytest/acceptance checks (pytest not installed)"
            }
        } catch {
            Skip "Optional pytest/acceptance checks (pytest not installed)"
        }
    } else {
        Skip "Optional pytest/acceptance checks (python or acceptance script missing)"
    }

    # 17) Optional default interactive EOF smoke (best-effort)
    # Uses cmd.exe input redirection from NUL to simulate immediate EOF.
    $EofOut = Join-Path $TempDir "eof_out.txt"
    $EofErr = Join-Path $TempDir "eof_err.txt"
    try {
        $cmd = "`"$ExePath`" < NUL 1> `"$EofOut`" 2> `"$EofErr`""
        & cmd.exe /c $cmd
        $rc = $LASTEXITCODE
        Pass "Default invocation EOF smoke (did not hang; rc=$rc)"
        Assert-NotContains $EofErr "Traceback (most recent call last)" "EOF smoke stderr has no traceback"
    } catch {
        Fail "Default invocation EOF smoke failed unexpectedly: $($_.Exception.Message)"
    }

}
finally {
    HR
    Write-Host "SUMMARY"
    Write-Host "  PASS: $($script:PassCount)"
    Write-Host "  FAIL: $($script:FailCount)"
    Write-Host "  SKIP: $($script:SkipCount)"
    HR
    if ($script:FailCount -eq 0) {
        Write-Host "Overall: PASS" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "Overall: FAIL" -ForegroundColor Red
        exit 1
    }
}