$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "[1/4] Building frontend production bundle..."
Push-Location frontend
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
Pop-Location

Write-Host "[2/4] Generating shared application icon..."
.\.venv\Scripts\python.exe -c "from pathlib import Path; from backend.icon import ensure_ico_file; ensure_ico_file(Path('build/app.ico'))"
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed" }

Write-Host "[3/4] Running PyInstaller (--onefile --windowed)..."
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

Write-Host "[4/4] Built dist\EdifierM60Control.exe"
Get-Item "dist\EdifierM60Control.exe" | Select-Object Name, Length, LastWriteTime
