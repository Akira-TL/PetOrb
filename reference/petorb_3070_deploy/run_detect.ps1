$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python scripts\detect.py
if (Test-Path scripts\run_val.py) { python scripts\run_val.py }
Write-Host "detect images: runs\detect"
Write-Host "val metrics:   runs\val"
