Set-Location $PSScriptRoot
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — please fill in your credentials."
}
uvicorn app.main:app --reload --port 8001
