$ErrorActionPreference = "Stop"

if (!(Test-Path "third_party\pict-src")) {
    Write-Error "third_party\pict-src not found!"
    exit 1
}

Write-Host "Building PICT for Windows x64..."

Push-Location third_party\pict-src

if (!(Test-Path "build")) {
    New-Item -ItemType Directory -Name "build" | Out-Null
}
cd build
cmake .. -A x64
cmake --build . --config Release
Pop-Location

$TargetDir = "vendor\pict\win-x64"
if (!(Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
}

$PictExeCandidates = @(
    "third_party\pict-src\build\Release\pict.exe",
    "third_party\pict-src\build\cli\Release\pict.exe",
    "third_party\pict-src\build\pict.exe"
)

$PictExe = $PictExeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $PictExe) {
    Write-Error "Could not find built pict.exe. Tried:`n$($PictExeCandidates -join "`n")"
    exit 1
}

Copy-Item -Path $PictExe -Destination "$TargetDir\pict.exe" -Force
Write-Host "Successfully built and copied PICT to $TargetDir\pict.exe"
