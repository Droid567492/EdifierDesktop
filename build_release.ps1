$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$AppVersion = (& .\.venv\Scripts\python.exe -c "from backend.version import APP_VERSION; print(APP_VERSION)").Trim()
if (-not $AppVersion) { throw "Could not determine APP_VERSION" }
Write-Host "==> Building Edifier M60 / M90 Studio Control v$AppVersion for Windows (x64)"

Write-Host "[1/5] Building frontend production bundle..."
Push-Location frontend
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
Pop-Location

Write-Host "[2/5] Generating shared application icon..."
.\.venv\Scripts\python.exe -c "from pathlib import Path; from backend.icon import ensure_ico_file; ensure_ico_file(Path('build/app.ico'))"
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed" }

Write-Host "[3/5] Running PyInstaller (--onefile --windowed)..."
.\.venv\Scripts\python.exe -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name EdifierM60Control `
  --icon build/app.ico `
  --add-data "frontend/dist;frontend/dist" `
  --collect-submodules bleak `
  --collect-submodules winrt `
  --collect-submodules pycaw `
  --collect-submodules comtypes `
  --collect-submodules uvicorn `
  --hidden-import pystray._win32 `
  launcher.py

if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

$PortableName = "dist\EdifierM60Control-v$AppVersion-win64-portable.exe"
Copy-Item "dist\EdifierM60Control.exe" $PortableName -Force
Write-Host "[4/5] Built portable executables: dist\EdifierM60Control.exe & $PortableName"

$IsccCandidates = @(
  (Get-Command iscc -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
  "C:\Program Files\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }

if ($IsccCandidates) {
  $Iscc = $IsccCandidates[0]
  Write-Host "[5/5] Compiling Windows installer via Inno Setup ($Iscc)..."
  & $Iscc "/DMyAppVersion=$AppVersion" "installer\windows\EdifierM60Control.iss"
  if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed" }
} else {
  Write-Host "[5/5] Inno Setup (ISCC.exe) not found locally; skipping setup.exe build."
}

Get-ChildItem "dist\*" -Include "*.exe" | Select-Object Name, Length, LastWriteTime
