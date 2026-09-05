#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR/.."

HOST_TEST='data/input/private_features.csv'
TEST_PATH='/data/input/private_features.csv'
if [ ! -f "$HOST_TEST" ]; then
  HOST_TEST='data/input/test_dataset.csv'
  TEST_PATH='/data/input/test_dataset.csv'
fi

if [ ! -f data/input/train_dataset.csv ]; then
  echo 'нет data/input/train_dataset.csv' >&2
  exit 1
fi
if [ ! -f "$HOST_TEST" ]; then
  echo 'нет private_features.csv или test_dataset.csv в data/input/' >&2
  exit 1
fi

echo '[1/6] compose'
docker compose config >/dev/null

echo '[2/6] build'
docker compose build

echo '[3/6] tests'
docker compose run --rm api python -m pytest -q /app/analytics/tests /app/backend/tests

echo '[4/6] train audit'
docker compose run --rm api florascope-core inspect --dataset /data/input/train_dataset.csv

echo '[5/6] model inference'
docker compose run --rm api florascope-core infer \
  --model /artifacts/competition_model \
  --input "$TEST_PATH" \
  --output /data/output

echo '[6/6] submission'
docker compose run --rm api florascope-core validate-submission \
  --test "$TEST_PATH" \
  --submission /data/output/submission.csv
