# pairwise-cli professor-style automated check suite (Windows PowerShell 5.1-safe)
# IMPORTANT:
# - This script intentionally uses native PowerShell invocation (& $Exe @Args) instead of a custom
#   ProcessStartInfo + manual quoting runner, because the latter caused argument corruption,
#   stdin pollution, hangs, and partial runs in Windows PowerShell 5.1.
# - This suite covers CLI robustness/contracts. Manual wizard abuse testing is still recommended.

[CmdletBinding()]
param(
    [string]$ExePath = ".\dist\pairwise-cli-win-x64.exe",
    [string]$ModelPath = ".\examples\sample.pict",
    [string]$VerifyFixturePath = ".\acceptance\fixtures\incomplete_cases.csv"
)

$ErrorActionPreference = "Stop"

# ------------------------------
# Global counters / temp files
# ------------------------------
$script:PassCount = 0
$script:FailCount = 0
$script:SkipCount = 0

$script:TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("pairwise-profcheck-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $script:TempDir -Force | Out-Null

$script:LastStdout = Join-Path $script:TempDir "last_stdout.txt"
$script:LastStderr = Join-Path $script:TempDir "last_stderr.txt"
$script:LastRc = -999

# ------------------------------
# Output helpers
# ------------------------------
function HR {
    Write-Host "------------------------------------------------------------"
}

function Pass([string]$Name) {
    $script:PassCount++
    Write-Host ("PASS: " + $Name) -ForegroundColor Green
}

function Fail([string]$Name) {
    $script:FailCount++
    Write-Host ("FAIL: " + $Name) -ForegroundColor Red
}

function Skip([string]$Name) {
    $script:SkipCount++
    Write-Host ("SKIP: " + $Name) -ForegroundColor Yellow
}

# ------------------------------
# Path helpers
# ------------------------------
function Resolve-PathSafe([string]$PathValue) {
    if ([string]::IsNullOrWhiteSpace($PathValue)) { return $PathValue }

    $p = $PathValue
    if ($PSScriptRoot -and -not [System.IO.Path]::IsPathRooted($p)) {
        $p = Join-Path $PSScriptRoot $p
    }

    try {
        return [System.IO.Path]::GetFullPath($p)
    } catch {
        return $p
    }
}

function Write-TextFile([string]$Path, [string]$Text) {
    if ($null -eq $Text) { $Text = "" }
    $Text | Out-File -FilePath $Path -Encoding utf8
}

# ------------------------------
# Assertions
# ------------------------------
function Assert-FileExists([string]$Path, [string]$Name) {
    if (Test-Path -LiteralPath $Path) {
        Pass $Name
    } else {
        Fail ("{0} (missing: {1})" -f $Name, $Path)
    }
}

function Assert-FileNonEmpty([string]$Path, [string]$Name) {
    if ((Test-Path -LiteralPath $Path) -and ((Get-Item -LiteralPath $Path).Length -gt 0)) {
        Pass $Name
    } else {
        Fail ("{0} (empty/missing: {1})" -f $Name, $Path)
    }
}

function Assert-Contains([string]$Path, [string]$Needle, [string]$Name, [switch]$CaseInsensitive) {
    if (-not (Test-Path -LiteralPath $Path)) {
        Fail ("{0} (file missing: {1})" -f $Name, $Path)
        return
    }

    $content = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
    if ($null -eq $content) { $content = "" }

    $ok = $false
    if ($CaseInsensitive) {
        $ok = $content.ToLower().Contains($Needle.ToLower())
    } else {
        $ok = $content.Contains($Needle)
    }

    if ($ok) {
        Pass $Name
    } else {
        Fail ("{0} (missing '{1}')" -f $Name, $Needle)
        ($content -split "`r?`n" | Select-Object -First 20 | ForEach-Object { "    $_" }) | Write-Host
    }
}

function Assert-NotContains([string]$Path, [string]$Needle, [string]$Name) {
    if (-not (Test-Path -LiteralPath $Path)) {
        # If stderr file doesn't exist, that's fine for "no traceback" checks.
        Pass $Name
        return
    }

    $content = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
    if ($null -eq $content) { $content = "" }

    if ($content.Contains($Needle)) {
        Fail ("{0} (found forbidden '{1}')" -f $Name, $Needle)
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
        Fail ("{0} (invalid JSON: {1})" -f $Name, $Path)
    }
}

function Assert-JsonPredicate([string]$Path, [string]$Name, [scriptblock]$Predicate) {
    try {
        $obj = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        $ok = & $Predicate $obj
        if ($ok) {
            Pass $Name
        } else {
            Fail ("{0} (predicate false)" -f $Name)
        }
    } catch {
        Fail ("{0} (JSON read/predicate error: {1})" -f $Name, $_.Exception.Message)
    }
}

function Assert-OutputContains([string]$Needle, [string]$Name, [switch]$CaseInsensitive) {
    $combined = ""
    if (Test-Path -LiteralPath $script:LastStdout) {
        $x = Get-Content -LiteralPath $script:LastStdout -Raw -ErrorAction SilentlyContinue
        if ($null -ne $x) { $combined += $x }
    }
    if (Test-Path -LiteralPath $script:LastStderr) {
        $y = Get-Content -LiteralPath $script:LastStderr -Raw -ErrorAction SilentlyContinue
        if ($null -ne $y) { $combined += "`n" + $y }
    }

    if ($null -eq $combined) { $combined = "" }

    $ok = $false
    if ($CaseInsensitive) {
        $ok = $combined.ToLower().Contains($Needle.ToLower())
    } else {
        $ok = $combined.Contains($Needle)
    }

    if ($ok) {
        Pass $Name
    } else {
        Fail ("{0} (missing '{1}')" -f $Name, $Needle)
        ($combined -split "`r?`n" | Select-Object -First 20 | ForEach-Object { "    $_" }) | Write-Host
    }
}

function Resolve-ExecutableForInvocation([string]$Exe) {
    if ([string]::IsNullOrWhiteSpace($Exe)) { return $Exe }

    # If it's already a path (relative or absolute), keep as-is.
    if ([System.IO.Path]::IsPathRooted($Exe) -or $Exe.Contains('\') -or $Exe.Contains('/')) {
        return $Exe
    }

    # Otherwise resolve through PATH (e.g., cmd.exe)
    try {
        $cmd = Get-Command $Exe -ErrorAction Stop | Select-Object -First 1
        if ($cmd -and $cmd.Path) { return $cmd.Path }
        if ($cmd -and $cmd.Source) { return $cmd.Source }
    } catch {
        # ignore, fallback below
    }

    return $Exe
}

# ------------------------------
# Native process invocation (PowerShell-safe)
# ------------------------------
function Invoke-Native {
    param(
        [Parameter(Mandatory=$true)][string]$Exe,
        [string[]]$Args = @()
    )

    # Reset capture files
    Write-TextFile -Path $script:LastStdout -Text ""
    Write-TextFile -Path $script:LastStderr -Text ""

    $resolvedExe = Resolve-ExecutableForInvocation $Exe

    # True existence check:
    # - if it's a path, Test-Path works
    # - if it's a PATH command, Resolve-ExecutableForInvocation should return full path
    if (-not (Test-Path -LiteralPath $resolvedExe)) {
        Write-TextFile -Path $script:LastStderr -Text ("Executable not found: " + $Exe)
        $script:LastRc = 126
        return [pscustomobject]@{
            ExitCode = 126
            StdOut = ""
            StdErr = ("Executable not found: " + $Exe)
            Command = ($Exe + " " + ($Args -join " "))
        }
    }

    $oldEAP = $ErrorActionPreference
    try {
        # IMPORTANT: In Windows PowerShell 5.1, native stderr can produce ErrorRecords.
        # With EAP=Stop, that incorrectly throws and causes false rc=125 in this harness.
        $ErrorActionPreference = "Continue"

        & $resolvedExe @Args 1> $script:LastStdout 2> $script:LastStderr

        if ($null -eq $LASTEXITCODE) {
            $script:LastRc = 0
        } else {
            $script:LastRc = [int]$LASTEXITCODE
        }
    } catch {
        # PowerShell-level failure to start or invoke the process
        $script:LastRc = 125
        Write-TextFile -Path $script:LastStderr -Text $_.ToString()
    } finally {
        $ErrorActionPreference = $oldEAP
    }

    $outText = ""
    $errText = ""
    if (Test-Path -LiteralPath $script:LastStdout) {
        $tmp = Get-Content -LiteralPath $script:LastStdout -Raw -ErrorAction SilentlyContinue
        if ($null -ne $tmp) { $outText = $tmp }
    }
    if (Test-Path -LiteralPath $script:LastStderr) {
        $tmp2 = Get-Content -LiteralPath $script:LastStderr -Raw -ErrorAction SilentlyContinue
        if ($null -ne $tmp2) { $errText = $tmp2 }
    }

    return [pscustomobject]@{
        ExitCode = [int]$script:LastRc
        StdOut   = $outText
        StdErr   = $errText
        Command  = ($resolvedExe + " " + ($Args -join " "))
    }
}


function Invoke-Capture {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][int[]]$ExpectedExitCodes,
        [Parameter(Mandatory=$true)][string]$Exe,
        [string[]]$Args = @()
    )

    $res = Invoke-Native -Exe $Exe -Args $Args

    if ($ExpectedExitCodes -contains [int]$res.ExitCode) {
        Pass ("{0} (rc={1})" -f $Name, $res.ExitCode)
        return $true
    } else {
        Fail ("{0} (rc={1}; expected {2})" -f $Name, $res.ExitCode, ($ExpectedExitCodes -join ','))
        Write-Host ("  Command: " + $res.Command)
        Write-Host "  --- stdout (first 20 lines) ---"
        ($res.StdOut -split "`r?`n" | Select-Object -First 20) | ForEach-Object { Write-Host ("    " + $_) }
        Write-Host "  --- stderr (first 20 lines) ---"
        ($res.StdErr -split "`r?`n" | Select-Object -First 20) | ForEach-Object { Write-Host ("    " + $_) }
        return $false
    }
}

function Have-VerifySubcommand {
    try {
        $res = Invoke-Native -Exe $script:ResolvedExePath -Args @('--help')
        $txt = ($res.StdOut + "`n" + $res.StdErr)
        return ($txt -match '(^|\s)verify(\s|$)')
    } catch {
        return $false
    }
}

# ------------------------------
# Main
# ------------------------------
$script:ResolvedExePath = Resolve-PathSafe $ExePath
$script:ResolvedModelPath = Resolve-PathSafe $ModelPath
$script:ResolvedVerifyFixturePath = Resolve-PathSafe $VerifyFixturePath

HR
Write-Host "pairwise-cli Windows Professor Check Suite"
Write-Host ("EXE      : " + $ExePath)
Write-Host ("Model    : " + $ModelPath)
Write-Host ("Temp dir : " + $script:TempDir)
HR
Write-Host ("Resolved EXE        : " + $script:ResolvedExePath)
Write-Host ("Resolved Model      : " + $script:ResolvedModelPath)
Write-Host ("Resolved VerifyCase : " + $script:ResolvedVerifyFixturePath)

try {
    # 0) Preconditions
    Assert-FileExists $script:ResolvedExePath "Windows EXE exists"
    Assert-FileNonEmpty $script:ResolvedExePath "Windows EXE is non-empty"
    Assert-FileExists $script:ResolvedModelPath "Sample model exists"

    if ((-not (Test-Path -LiteralPath $script:ResolvedExePath)) -or (-not (Test-Path -LiteralPath $script:ResolvedModelPath))) {
        throw "PreflightFailed: missing EXE or sample model"
    }

    # 1) Help surfaces / contract presence
    Invoke-Capture -Name "Root --help" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @('--help') | Out-Null
    Assert-OutputContains "generate" "Root help lists generate"
    Assert-OutputContains "doctor" "Root help lists doctor"

    Invoke-Capture -Name "generate --help" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @('generate','--help') | Out-Null
    Assert-OutputContains "--verify" "generate help shows --verify"
    Assert-OutputContains "--no-verify" "generate help shows --no-verify"
    Assert-OutputContains "--early-stop" "generate help shows --early-stop"
    Assert-OutputContains "--no-early-stop" "generate help shows --no-early-stop"
    Assert-OutputContains "--total-timeout-sec" "generate help shows --total-timeout-sec"
    Assert-OutputContains "--max-tries" "generate help shows --max-tries"

    $hasVerify = Have-VerifySubcommand
    if ($hasVerify) {
        Invoke-Capture -Name "verify --help" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @('verify','--help') | Out-Null
    } else {
        Skip "verify subcommand help (subcommand not present)"
    }

    # 2) doctor
    Invoke-Capture -Name "doctor" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @('doctor') | Out-Null
    Assert-Contains $script:LastStdout "PICT Execution" "doctor output contains PICT Execution"
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "doctor stderr has no traceback"

    # 3) Verified generation (auto-order, deterministic)
    $OutJson = Join-Path $script:TempDir "out_verified.json"
    Invoke-Capture -Name "generate verified auto deterministic json" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--format','json',
        '--verify','--early-stop','--ordering','auto',
        '--tries','200','--seed','0','--deterministic'
    ) | Out-Null
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
    $OutNoVerify = Join-Path $script:TempDir "out_noverify.json"
    Invoke-Capture -Name "generate no-verify json" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--format','json','--no-verify'
    ) | Out-Null
    Copy-Item $script:LastStdout $OutNoVerify -Force
    Assert-JsonParseable $OutNoVerify "No-verify JSON parses"
    Assert-JsonPredicate $OutNoVerify "metadata.verified == false under --no-verify" { param($j) $j.metadata.verified -eq $false }
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "No-verify stderr has no traceback"

    # 5) JSON purity under verbose logging
    $OutVerbose = Join-Path $script:TempDir "out_verbose.json"
    $ErrVerbose = Join-Path $script:TempDir "out_verbose.err"
    Invoke-Capture -Name "generate json verbose purity" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--format','json','--verbose'
    ) | Out-Null
    Copy-Item $script:LastStdout $OutVerbose -Force
    Copy-Item $script:LastStderr $ErrVerbose -Force
    Assert-JsonParseable $OutVerbose "Verbose stdout still valid JSON"
    Assert-FileNonEmpty $ErrVerbose "Verbose logs go to stderr (non-empty stderr)"
    Assert-NotContains $ErrVerbose "Traceback (most recent call last)" "Verbose stderr has no traceback"

    # 6) Determinism
    $Det1 = Join-Path $script:TempDir "det1.json"
    $Det2 = Join-Path $script:TempDir "det2.json"
    Invoke-Capture -Name "determinism run #1" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--format','json',
        '--verify','--early-stop','--ordering','auto',
        '--tries','200','--seed','123','--deterministic'
    ) | Out-Null
    Copy-Item $script:LastStdout $Det1 -Force

    Invoke-Capture -Name "determinism run #2" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--format','json',
        '--verify','--early-stop','--ordering','auto',
        '--tries','200','--seed','123','--deterministic'
    ) | Out-Null
    Copy-Item $script:LastStdout $Det2 -Force

    if ((Get-FileHash $Det1).Hash -eq (Get-FileHash $Det2).Hash) {
        Pass "Determinism: identical JSON for same seed/flags"
    } else {
        Fail "Determinism: outputs differ"
    }

    # 7) Ordering modes
    $KeepJson = Join-Path $script:TempDir "keep.json"
    Invoke-Capture -Name "generate ordering=keep" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--format','json',
        '--verify','--early-stop','--ordering','keep',
        '--tries','50','--seed','0','--deterministic'
    ) | Out-Null
    Copy-Item $script:LastStdout $KeepJson -Force
    Assert-JsonParseable $KeepJson "Ordering keep JSON parses"
    Assert-JsonPredicate $KeepJson "metadata.ordering_mode == keep" { param($j) [string]$j.metadata.ordering_mode -eq 'keep' }

    $KeepAliasJson = Join-Path $script:TempDir "keep_alias.json"
    Invoke-Capture -Name "generate --keep-order alias" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--format','json',
        '--verify','--early-stop','--keep-order',
        '--tries','50','--seed','0','--deterministic'
    ) | Out-Null
    Copy-Item $script:LastStdout $KeepAliasJson -Force
    Assert-JsonParseable $KeepAliasJson "keep-order alias JSON parses"
    Assert-JsonPredicate $KeepAliasJson "keep-order alias yields keep ordering metadata" { param($j) [string]$j.metadata.ordering_mode -eq 'keep' }

    # 8) CSV generation + verify success (if verify exists)
    $CsvOut = Join-Path $script:TempDir "generated_cases.csv"
    Invoke-Capture -Name "generate csv to file" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--format','csv',
        '--out',$CsvOut,'--verify','--early-stop','--ordering','auto',
        '--tries','100','--seed','0','--deterministic'
    ) | Out-Null
    Assert-FileNonEmpty $CsvOut "CSV file generated"
    $firstLine = ""
    try { $firstLine = Get-Content -LiteralPath $CsvOut -TotalCount 1 } catch { $firstLine = "" }
    if ($firstLine -match ',') { Pass "Generated CSV header appears CSV-like" } else { Fail "Generated CSV header not CSV-like" }

    if ($hasVerify) {
        Invoke-Capture -Name "verify generated CSV succeeds" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @(
            'verify','--model',$script:ResolvedModelPath,'--cases',$CsvOut
        ) | Out-Null
        Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "verify success stderr has no traceback"
    } else {
        Skip "verify generated CSV succeeds (verify subcommand not present)"
    }

    # 9) Validation error paths (exit 2)
    Invoke-Capture -Name "validation: strength < 2 => exit 2" -ExpectedExitCodes @(2) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--strength','1'
    ) | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "strength validation has no traceback"

    Invoke-Capture -Name "validation: tries=0 => exit 2" -ExpectedExitCodes @(2) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--tries','0'
    ) | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "tries=0 validation has no traceback"

    Invoke-Capture -Name "validation: tries > max-tries => exit 2" -ExpectedExitCodes @(2) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--tries','999999','--max-tries','10'
    ) | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "tries bound validation has no traceback"

    Invoke-Capture -Name "validation: pict-timeout-sec <= 0 => exit 2" -ExpectedExitCodes @(2) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--pict-timeout-sec','0'
    ) | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "pict-timeout validation has no traceback"

    Invoke-Capture -Name "validation: total-timeout-sec <= 0 => exit 2" -ExpectedExitCodes @(2) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--total-timeout-sec','0'
    ) | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "total-timeout validation has no traceback"

    # 10) Warning path: total timeout < pict-timeout (may still succeed or timeout)
    $WarnOut = Join-Path $script:TempDir "warn.json"
    $WarnErr = Join-Path $script:TempDir "warn.err"
    Invoke-Capture -Name "warning path total-timeout < pict-timeout" -ExpectedExitCodes @(0,5) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--format','json',
        '--tries','1','--pict-timeout-sec','10','--total-timeout-sec','0.5'
    ) | Out-Null
    Copy-Item $script:LastStdout $WarnOut -Force
    Copy-Item $script:LastStderr $WarnErr -Force
    Assert-Contains $WarnErr "warning" "Warning emitted when total-timeout < pict-timeout" -CaseInsensitive
    if ($script:LastRc -eq 0) {
        Assert-JsonParseable $WarnOut "Warning path stdout valid JSON when generation succeeds"
    }
    Assert-NotContains $WarnErr "Traceback (most recent call last)" "Warning path stderr has no traceback"

    # 11) Timeout paths (exit 5)
    $perPictTimeoutObserved = $false
    foreach ($tv in @('0.0005','0.0001')) {
        Invoke-Capture -Name ("timeout: per-PICT timeout " + $tv) -ExpectedExitCodes @(5) -Exe $script:ResolvedExePath -Args @(
            'generate','--model',$script:ResolvedModelPath,
            '--pict-timeout-sec',$tv,'--tries','50','--format','json','--no-early-stop'
        ) | Out-Null
        if ($script:LastRc -eq 5) {
            $perPictTimeoutObserved = $true
            break
        }
    }
    if ($perPictTimeoutObserved) {
        Pass "per-PICT adaptive timeout observed exit 5"
    } else {
        Fail ("per-PICT adaptive timeout did not exit 5 (last rc={0})" -f $script:LastRc)
    }
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "per-PICT timeout path has no traceback"

    Invoke-Capture -Name "timeout: tiny total timeout => exit 5" -ExpectedExitCodes @(5) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--total-timeout-sec','0.01','--tries','500','--format','json'
    ) | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "total timeout path has no traceback"

    # 12) Verify failure path (exit 4) on incomplete fixture
    if ($hasVerify -and (Test-Path -LiteralPath $script:ResolvedVerifyFixturePath)) {
        Invoke-Capture -Name "verify incomplete fixture => exit 4" -ExpectedExitCodes @(4) -Exe $script:ResolvedExePath -Args @(
            'verify','--model',$script:ResolvedModelPath,'--cases',$script:ResolvedVerifyFixturePath
        ) | Out-Null
        Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "verify failure path has no traceback"

        $combined = ""
        try {
            $combined += (Get-Content -LiteralPath $script:LastStdout -Raw -ErrorAction SilentlyContinue)
            $combined += "`n"
            $combined += (Get-Content -LiteralPath $script:LastStderr -Raw -ErrorAction SilentlyContinue)
        } catch {}

        $foundDiag = $false
        foreach ($pat in @('missing pair','missing pairs','coverage verification failed','missing')) {
            if ($combined -match $pat) { $foundDiag = $true; break }
        }
        if ($foundDiag) {
            Pass "Verify failure reports missing pairs/details"
        } else {
            Fail "Verify failure missing-pair diagnostics not found"
        }
    } else {
        Skip "verify incomplete fixture => exit 4 (verify subcommand or fixture missing)"
    }

    # 13) Strength != 2 semantics (lb should be null)
    $S3Out = Join-Path $script:TempDir "strength3.json"
    Invoke-Capture -Name "strength=3 JSON generation" -ExpectedExitCodes @(0) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$script:ResolvedModelPath,'--strength','3','--format','json','--no-verify'
    ) | Out-Null
    Copy-Item $script:LastStdout $S3Out -Force
    Assert-JsonParseable $S3Out "Strength=3 JSON parses"
    Assert-JsonPredicate $S3Out "Strength=3 metadata.lb is null" { param($j) $null -eq $j.metadata.lb }

    # 14) Missing/malformed/non-UTF8 model handling (no traceback)
    $MissingModel = Join-Path $script:TempDir "does_not_exist.pict"
    Invoke-Capture -Name "missing model path handled" -ExpectedExitCodes @(2,3) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$MissingModel,'--format','json'
    ) | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "Missing model path has no traceback"

    $BadModel = Join-Path $script:TempDir "bad_model.pict"
    @(
        "This is not a valid PICT model",
        "No colon here maybe"
    ) | Set-Content -LiteralPath $BadModel -Encoding utf8
    Invoke-Capture -Name "malformed model file handled" -ExpectedExitCodes @(2,3) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$BadModel,'--format','json'
    ) | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "Malformed model file has no traceback"

    $BadUtf8 = Join-Path $script:TempDir "bad_utf8_model.pict"
    [System.IO.File]::WriteAllBytes($BadUtf8, [byte[]](0xFF,0xFE,0xFA,0xFB))
    Invoke-Capture -Name "non-UTF8 model file handled" -ExpectedExitCodes @(2,3) -Exe $script:ResolvedExePath -Args @(
        'generate','--model',$BadUtf8,'--format','json'
    ) | Out-Null
    Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "Non-UTF8 model file has no traceback"

    # 15) Malformed verify inputs (if verify exists)
    if ($hasVerify) {
        $EmptyCsv = Join-Path $script:TempDir "empty_cases.csv"
        New-Item -ItemType File -Path $EmptyCsv -Force | Out-Null
        Invoke-Capture -Name "verify empty CSV handled" -ExpectedExitCodes @(2,3,4) -Exe $script:ResolvedExePath -Args @(
            'verify','--model',$script:ResolvedModelPath,'--cases',$EmptyCsv
        ) | Out-Null
        Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "verify empty CSV has no traceback"

        $BadCasesJson = Join-Path $script:TempDir "bad_cases.json"
        "{ this is not json }" | Set-Content -LiteralPath $BadCasesJson -Encoding utf8
        Invoke-Capture -Name "verify malformed JSON handled" -ExpectedExitCodes @(2,3,4) -Exe $script:ResolvedExePath -Args @(
            'verify','--model',$script:ResolvedModelPath,'--cases',$BadCasesJson
        ) | Out-Null
        Assert-NotContains $script:LastStderr "Traceback (most recent call last)" "verify malformed JSON has no traceback"
    } else {
        Skip "Malformed verify input checks (verify subcommand not present)"
    }

    # 16) Optional pytest / acceptance evidence (skip if unavailable)
    $hasPython = $false
    $PythonCmd = $null

    try {
        & py -3.11 -c "print('ok')" *> $null
        if ($LASTEXITCODE -eq 0) {
            $hasPython = $true
            $PythonCmd = "py -3.11"
        }
    } catch {}

    if (-not $hasPython) {
        try {
            & python -c "print('ok')" *> $null
            if ($LASTEXITCODE -eq 0) {
                $hasPython = $true
                $PythonCmd = "python"
            }
        } catch {}
    }

    $AcceptanceRunnerPath = Resolve-PathSafe ".\acceptance\run_acceptance.py"

    if ($hasPython -and (Test-Path -LiteralPath $AcceptanceRunnerPath)) {
        try {
            & cmd.exe /c ($PythonCmd + " -m pytest --version") *> $null
            if ($LASTEXITCODE -eq 0) {
                Invoke-Capture -Name "pytest acceptance marker (optional)" -ExpectedExitCodes @(0) -Exe "cmd.exe" -Args @(
                    '/c', ($PythonCmd + " -m pytest -m acceptance -q")
                ) | Out-Null

                Invoke-Capture -Name "acceptance runner exe mode (optional)" -ExpectedExitCodes @(0) -Exe "cmd.exe" -Args @(
                    '/c', ($PythonCmd + " acceptance/run_acceptance.py --mode exe --timeout-sec 60")
                ) | Out-Null
            } else {
                Skip "Optional pytest/acceptance checks (pytest not installed)"
            }
        } catch {
            Skip "Optional pytest/acceptance checks (pytest not installed)"
        }
    } else {
        Skip "Optional pytest/acceptance checks (python or acceptance script missing)"
    }

    # 17) Optional default invocation EOF smoke (best effort)
    # Use cmd.exe + input redirection from NUL to simulate immediate EOF.
    $EofOut = Join-Path $script:TempDir "eof_out.txt"
    $EofErr = Join-Path $script:TempDir "eof_err.txt"
    $cmdLine = '"' + $script:ResolvedExePath + '" < NUL 1> "' + $EofOut + '" 2> "' + $EofErr + '"'

    Invoke-Capture -Name "Default invocation EOF smoke" `
        -ExpectedExitCodes @(0,1,2,3,4,5) `
        -Exe "cmd.exe" `
        -Args @('/c', $cmdLine) | Out-Null

    Assert-FileExists $EofOut "EOF smoke stdout file exists"
    Assert-FileExists $EofErr "EOF smoke stderr file exists"
    Assert-NotContains $EofErr "Traceback (most recent call last)" "EOF smoke stderr has no traceback"


} catch {
    Fail ("Unhandled exception in suite: " + $_.ToString())
    try {
        $_.ToString() | Out-File -FilePath $script:LastStderr -Encoding utf8 -Append
    } catch {}
} finally {
    HR
    Write-Host "SUMMARY"
    Write-Host ("  PASS: " + $script:PassCount)
    Write-Host ("  FAIL: " + $script:FailCount)
    Write-Host ("  SKIP: " + $script:SkipCount)
    HR

    if ($script:FailCount -eq 0) {
        Write-Host "Overall: PASS" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "Overall: FAIL" -ForegroundColor Red
        exit 1
    }
}