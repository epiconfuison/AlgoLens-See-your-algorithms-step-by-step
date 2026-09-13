$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path '.venv/Scripts/python.exe')) { throw '请先运行 setup.ps1' }
& ./.venv/Scripts/python.exe -m algoviz
