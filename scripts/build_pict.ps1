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

$PictExe = "third_party\pict-src\build\Release\pict.exe"
if (!(Test-Path $PictExe)) {
    $PictExe = "third_party\pict-src\build\pict.exe"
}

Copy-Item -Path $PictExe -Destination "$TargetDir\pict.exe" -Force
Write-Host "Successfully built and copied PICT to $TargetDir\pict.exe"
