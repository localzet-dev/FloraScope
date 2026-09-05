# запуск на Windows / Linux / macOS

Нормальный entrypoint для всех ОС — Docker Compose. Python/Node/GDAL/LightGBM на хост ставить не надо.

## перед стартом

Нужно:

- Docker Desktop на Windows/macOS или Docker Engine на Linux;
- Docker Compose v2 (`docker compose`, не старый `docker-compose`);
- 16 GB RAM минимум, лучше 24–32 GB;
- свободные порты 8080 и 8000 (или поменять в `.env`).

## Windows 10/11

PowerShell из корня проекта:

```powershell
Copy-Item .env.example .env
.\scripts\start.ps1
```

Если execution policy не даёт запустить файл:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

Ручной вариант тоже всегда работает:

```powershell
docker compose build
docker compose up -d
```

## Ubuntu / другой Linux

```bash
cp .env.example .env
./scripts/start.sh
```

Если после работы контейнера файлы в `data/output` принадлежат root — это только вопрос ownership bind-mount. Можно
вернуть себе владельца:

```bash
sudo chown -R "$USER":"$USER" data artifacts
```

На вычисления это не влияет.

## macOS Intel / Apple Silicon

```bash
cp .env.example .env
./scripts/start.sh
```

Base compose не фиксирует архитектуру и должен собираться native (`linux/amd64` на Intel, `linux/arm64` на Apple
Silicon). Критичные бинарные зависимости зафиксированы на версиях с Linux ARM64 wheels (в частности LightGBM 4.6.0 и
Rasterio 1.5.1).

Если на конкретной ARM-машине какая-то бинарная Python-зависимость внезапно не соберётся, есть fallback через
x86-эмуляцию Docker Desktop:

```bash
docker compose -f docker-compose.yml -f docker-compose.amd64.yml build
docker compose -f docker-compose.yml -f docker-compose.amd64.yml up -d
```

Это медленнее, поэтому использовать только как запасной вариант.

## после запуска

```text
Web      http://localhost:8080
OpenAPI  http://localhost:8000/docs
```

Проверка релиза:

Linux/macOS:

```bash
./scripts/check_release.sh
```

Windows:

```powershell
.\scripts\check_release.ps1
```

## почему SQLite не лежит в ./data

Runtime DB вынесена в named Docker volume `florascope_state`. На Windows/macOS это надёжнее, чем SQLite WAL поверх host
bind mount. Train/test, submission, raster outputs и model artifacts по-прежнему лежат в обычных каталогах проекта и
видны с хоста.

## пути

В документации вида `/data/...` — это **пути внутри контейнера**, они одинаковые на Windows/Linux/macOS. На хосте всегда
используются относительные каталоги проекта:

```text
data/input/
data/output/
data/live/
artifacts/
```

Никаких `C:\...`, `/home/...` или `/Users/...` в application config быть не должно.

## Если внешние API доступны на хосте, но не в контейнере

Прокси браузера или shell хоста не обязательно передаётся Docker. Можно настроить proxy в Docker Desktop либо задать в
`.env` необязательные `FLORASCOPE_HTTP_PROXY` и `FLORASCOPE_HTTPS_PROXY`, затем пересоздать API:
`docker compose up -d api`.

Адрес должен быть доступен из контейнера: `127.0.0.1` внутри него означает сам контейнер. Для доступного прокси хоста
предусмотрен alias `host.docker.internal` (также Linux через host-gateway). Если прокси слушает только loopback хоста,
alias сам по себе этого не исправит; нужен доступный контейнеру endpoint или настройка Docker Desktop. Учётные данные
прокси остаются только в локальном `.env`.

Доступность каталога STAC не доказывает доступность самих COG; проверять нужно оба этапа. Даже при частичном отказе
acquisition сохраняет manifest в `data/live/<analysis_id>/acquisition.json`.
