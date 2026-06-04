param(
    [string]$InstallRoot = "D:\tools\exiftool",
    [string]$DownloadUrl = "https://exiftool.org/exiftool-13.52_64.zip"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$downloadDir = Join-Path (Split-Path $InstallRoot -Parent) "downloads"
$zipPath = Join-Path $downloadDir "exiftool-13.52_64.zip"

New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
if (Test-Path $InstallRoot) {
    Remove-Item $InstallRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null

Invoke-WebRequest -Uri $DownloadUrl -OutFile $zipPath -UseBasicParsing
Expand-Archive -Path $zipPath -DestinationPath $InstallRoot -Force

$exe = Get-ChildItem $InstallRoot -Recurse -Filter "exiftool*.exe" | Sort-Object FullName | Select-Object -First 1
if (-not $exe) {
    throw "ExifTool executable not found after extraction."
}

$targetExe = Join-Path $InstallRoot "exiftool.exe"
Copy-Item $exe.FullName $targetExe -Force

$filesDir = Get-ChildItem $exe.Directory.FullName -Directory | Where-Object { $_.Name -like "exiftool_files*" } | Select-Object -First 1
if ($filesDir) {
    $targetFilesDir = Join-Path $InstallRoot "exiftool_files"
    if ($filesDir.FullName -ne $targetFilesDir) {
        if (Test-Path $targetFilesDir) {
            Remove-Item $targetFilesDir -Recurse -Force
        }
        Copy-Item $filesDir.FullName $targetFilesDir -Recurse -Force
    }
}

& $targetExe -ver
