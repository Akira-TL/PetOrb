param(
    [int]$Port = 8010,
    [int]$AdbServerPort = 5037,
    [string]$Adb = "adb"
)

$ErrorActionPreference = "Stop"
& $Adb -P $AdbServerPort devices
& $Adb -P $AdbServerPort reverse "tcp:$Port" "tcp:$Port"
Write-Host "[PetOrb] USB reverse ready: Android 127.0.0.1:$Port -> PC 127.0.0.1:$Port"
