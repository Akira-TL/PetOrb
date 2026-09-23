$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== PetOrb competition Web UI ==="
Write-Host "1) Phone USB to this PC, USB debugging ON"
Write-Host "2) This script: adb reverse + web UI"
Write-Host "3) Tech http://127.0.0.1:8080   User http://127.0.0.1:8081"
Write-Host "4) Demo preview -> tap send-to-PC"
Write-Host ""

function Find-Adb {
    $candidates = @(
        (Get-Command adb -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
        "$PSScriptRoot\..\tools\platform-tools\adb.exe",
        "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe",
        "$env:ANDROID_HOME\platform-tools\adb.exe",
        "$env:ANDROID_SDK_ROOT\platform-tools\adb.exe",
        "D:\Android\Sdk\platform-tools\adb.exe",
        "F:\Android\Sdk\platform-tools\adb.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

$adb = Find-Adb
if (-not $adb) {
    Write-Host "adb not found. Install Android platform-tools, or add adb to PATH."
    exit 1
}

Write-Host "adb: $adb"
& $adb start-server
& $adb devices
& $adb reverse tcp:8080 tcp:8080
if ($LASTEXITCODE -ne 0) {
    Write-Host "adb reverse not ready (plug in the phone, enable USB debugging, then rerun this script)."
    Write-Host "Starting web server anyway so the page can load."
} else {
    Write-Host "adb reverse tcp:8080 tcp:8080 OK"
}

$py = "C:\Users\LENOVO\.conda\envs\diffir2vr\python.exe"
if (-not (Test-Path $py)) {
    $py = "python"
}
Write-Host "python: $py"
Write-Host "open http://127.0.0.1:8080"
$env:PYTHONPATH = ""
$env:PYTHONUNBUFFERED = "1"
& $py -u scripts\pc_detect_web_server.py @args
