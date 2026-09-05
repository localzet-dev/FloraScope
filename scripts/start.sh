#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR/.."

if ! command -v docker >/dev/null 2>&1; then
  echo 'docker не найден. Нужен Docker Engine / Docker Desktop.' >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo 'docker установлен, но daemon не отвечает. Запустите Docker Desktop/Engine.' >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo 'нужен Docker Compose v2: команда `docker compose`.' >&2
  exit 1
fi

[ -f .env ] || cp .env.example .env

printf 'host: '
uname -srm 2>/dev/null || true
printf 'docker: '
docker version --format '{{.Server.Version}}' 2>/dev/null || true
printf 'compose: '
docker compose version --short 2>/dev/null || true

docker compose build
docker compose up -d

echo 'ждём API...'
i=0
while [ "$i" -lt 30 ]; do
  if docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)" >/dev/null 2>&1; then
    echo 'API: ok'
    echo 'Web: http://localhost:8080'
    echo 'OpenAPI: http://localhost:8000/docs'
    exit 0
  fi
  i=$((i + 1))
  sleep 2
done

echo 'API не стал healthy за ~60 секунд. Последние логи:' >&2
docker compose logs --tail=120 api >&2
exit 1
