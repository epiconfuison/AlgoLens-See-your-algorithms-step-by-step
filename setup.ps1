$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$basePython = (python -c "import sys; print(sys.base_prefix)").Trim()
if (Test-Path "$basePython/Library/bin") { $env:PATH = "$basePython/Library/bin;" + $env:PATH }
if (!(Test-Path '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建虚拟环境失败' }
}
& ./.venv/Scripts/python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw '安装依赖失败' }
& ./.venv/Scripts/python.exe -m algoviz.environment
if ($LASTEXITCODE -ne 0) { throw '环境验证失败' }

