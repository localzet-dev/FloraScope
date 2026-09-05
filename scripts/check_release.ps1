$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$testContainerPath = "/data/input/private_features.csv"
if (-not (Test-Path "data/input/private_features.csv")) {
    $testContainerPath = "/data/input/test_dataset.csv"
}

if (-not (Test-Path "data/input/train_dataset.csv")) {
    throw "нет data/input/train_dataset.csv"
}
if (-not ((Test-Path "data/input/private_features.csv") -or (Test-Path "data/input/test_dataset.csv"))) {
    throw "нет private_features.csv или test_dataset.csv в data/input/"
}

Write-Host "[1/6] compose"
docker compose config *> $null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[2/6] build"
docker compose build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[3/6] tests"
docker compose run --rm api python -m pytest -q /app/analytics/tests /app/backend/tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[4/6] train audit"
docker compose run --rm api florascope-core inspect --dataset /data/input/train_dataset.csv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[5/6] model inference"
docker compose run --rm api florascope-core infer `
    --model /artifacts/competition_model `
    --input $testContainerPath `
    --output /data/output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[6/6] submission"
docker compose run --rm api florascope-core validate-submission `
    --test $testContainerPath `
    --submission /data/output/submission.csv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
