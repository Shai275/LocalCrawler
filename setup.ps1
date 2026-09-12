param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& $Python -c "import sys; assert sys.version_info >= (3, 12), 'Python 3.12 or later is required'"
if ($LASTEXITCODE -ne 0) { throw 'Please install Python 3.12 with Tcl/Tk first.' }
& $Python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Could not create the project environment.' }
$ProjectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $ProjectPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $ProjectPython -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Browser installation failed.' }
& $ProjectPython doctor.py
Write-Host 'Ready. Run launch.cmd. For AI, start Ollama and run: ollama pull qwen2.5:7b'
