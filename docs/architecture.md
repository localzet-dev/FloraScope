# architecture

Не микросервисы. Просто три нормальные границы:

```text
frontend (React)
    |
    | REST / JSON / XYZ tiles
    v
backend (FastAPI)
    |
    | python package API
    v
analytics (ML + EO + raster)
```

## analytics

Не знает про HTTP/React/SQLite. Можно гонять его отдельно:

```bash
cd analytics
python -m pytest
florascope-core benchmark ...
```

Внутри две ветки:

- competition gap recovery;
- live EO/anomaly processing.

## backend

FastAPI занимается только orchestration:

- `/api/v1/fields` — полигоны;
- `/api/v1/analyses` — live jobs/results/tiles;
- `/api/v1/benchmark` — organizer files/model run/report;
- `/api/v1/jobs` — progress.

Metadata/jobs лежат в SQLite. Растры, model artifacts и CSV — файлами. Для одного ноутбука PostGIS/Redis тут просто
лишние точки отказа.

Job executor внутри backend, `max_workers=1`. Нам не нужна очередь уровня продового SaaS, зато UI не блокирует
HTTP-request на обучении/EO.

## frontend

Отдельная Vite/React сборка, nginx в production. Backend внутрь frontend Docker image не кладём.

Экранов по сути три:

- мониторинг поля;
- model / benchmark;
- короткая research выжимка.

## почему 20 м

NDVI можно считать на 10 м, но NDRE/NDMI/NBR требуют red-edge/SWIR с нативными 20 м. Поэтому общая аналитическая сетка
20 м честнее, чем рисовать «10 м» после обычного resampling.
