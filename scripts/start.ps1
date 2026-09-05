$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker не найден. Нужен Docker Desktop."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "docker установлен, но daemon не отвечает. Запустите Docker Desktop."
}

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Нужен Docker Compose v2: команда 'docker compose'."
}

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}

Write-Host "host: Windows / PowerShell"
docker version --format "docker: {{.Server.Version}}"
docker compose version

docker compose build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose up -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "ждём API..."
for ($i = 0; $i -lt 30; $i++) {
    docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)" *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "API: ok"
        Write-Host "Web: http://localhost:8080"
        Write-Host "OpenAPI: http://localhost:8000/docs"
        exit 0
    }
    Start-Sleep -Seconds 2
}

Write-Host "API не стал healthy за ~60 секунд. Последние логи:" -ForegroundColor Red
docker compose logs --tail=120 api
exit 1
