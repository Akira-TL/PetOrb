param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 9000,
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "apps\detector")
& $Python -m uvicorn petorb_detector.main:app --host $HostAddress --port $Port
