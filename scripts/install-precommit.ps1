Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

python -m pre_commit install
Write-Host "pre-commit hook installed."
