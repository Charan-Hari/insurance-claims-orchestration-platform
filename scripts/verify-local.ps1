$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "Compiling Python services..."
python -m compileall -q services\policy\src services\claims\src services\orchestrator\src services\legacy-adapter\src

Write-Host "Running Python contract and unit tests..."
$env:DATABASE_URL = "postgresql+asyncpg://policy_user:policy_dev_password@localhost:5432/policy_db"
python -m pytest -q services\policy\tests\contract
$env:DATABASE_URL = "postgresql+asyncpg://policy_user:policy_dev_password@localhost:5432/claims_db"
$env:POLICY_SERVICE_BASE_URL = "http://localhost:8000"
python -m pytest -q services\claims\tests\contract
python -m pytest -q services\orchestrator\tests services\legacy-adapter\tests

if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host "Running Payments tests..."
    Push-Location services\payments
    try {
        npm ci
        npm test
    }
    finally {
        Pop-Location
    }
}

Write-Host "Local verification passed. Docker Compose validation requires Docker."
