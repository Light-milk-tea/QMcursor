# Build QMcursor onedir package and zip for GitHub Releases.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

& $Python -m pip install -e ".[build]" | Out-Host

$Spec = Join-Path $Root "QMcursor.spec"
@"
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('src/arkcursor/themes', 'arkcursor/themes')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    ['run.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='QMcursor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='QMcursor',
)
"@ | Set-Content -Path $Spec -Encoding UTF8

& $Python -m PyInstaller --noconfirm --clean $Spec | Out-Host

$DistDir = Join-Path $Root "dist\QMcursor"
$Exe = Join-Path $DistDir "QMcursor.exe"
if (-not (Test-Path $Exe)) {
    throw "Build failed: missing $Exe"
}

$ReleaseDir = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$Zip = Join-Path $ReleaseDir "QMcursor-windows.zip"
if (Test-Path $Zip) {
    Remove-Item $Zip -Force
}

if (Test-Path $Zip) {
    Remove-Item $Zip -Force
}
Push-Location $DistDir
try {
    tar -a -cf $Zip *
} finally {
    Pop-Location
}
if (-not (Test-Path $Zip)) {
    throw "Zip failed: missing $Zip"
}
Write-Host "OK $Zip"
Get-Item $Zip | Format-List FullName, Length, LastWriteTime
