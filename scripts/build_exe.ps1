$ErrorActionPreference = "Stop"

$Target = "win-x64"
Write-Host "Building PyInstaller executable for $Target..."

pyinstaller --noconfirm --onefile --console `
  --name "pairwise-cli-$Target" `
  --add-data "vendor\pict\$Target\*;vendor\pict\$Target" `
  --add-data "THIRD_PARTY_NOTICES.txt;." `
  pairwise_cli\__main__.py

Write-Host "Done! Executable is in dist/"
