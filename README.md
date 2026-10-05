# FloraScope

Веб-сервис для восстановления пропусков `primary_ndvi` и поиска негативных периодов вегетации.

У проекта две независимые точки входа, как в постановке:

1. web: выбираем/рисуем поле → сервис сам ищет спутниковые + погодные данные → строит ряд и события;
2. batch: `private_features.csv` → `submission.csv` для `is_synthetic_gap=True`.

## что внутри

```text
analytics/   gap recovery, anomaly detection, EO/raster processing
backend/     FastAPI, SQLite, jobs, API
frontend/    React + TypeScript + MapLibre + ECharts
research/    отчёт и результаты экспериментов
notes/       наши короткие рабочие заметки
data/        organizer train/test + runtime output
artifacts/   готовая competition model после обучения
```

Стек: Python 3.12, FastAPI, pandas/numpy/scipy, LightGBM, Rasterio/Shapely/PyProj, React 19, TypeScript, MapLibre,
ECharts, Mantine, nginx, Docker Compose.

## быстрый запуск

Windows PowerShell:

```powershell
Copy-Item .env.example .env
.\scripts\start.ps1
```

Ubuntu/macOS:

```bash
cp .env.example .env
./scripts/start.sh
```

Ручные `docker compose build` / `docker compose up -d` тоже работают. Подробнее: `docs/run_cross_platform.md`.

Web: http://localhost:8080  
API/OpenAPI: http://localhost:8000/docs

`web` и `api` — отдельные контейнеры. Фронт намеренно не зависит от healthcheck backend при старте: если API
перезапускается, интерфейс всё равно открывается.

## работа в интерфейсе

Тёмное рабочее пространство разделено на «Мониторинг», «Восстановление» и «Метод и проверка».
В мониторинге выберите территорию и сохранённый анализ либо задайте период нового сбора.
Режимы «Обзор / Карта / Динамика» меняют рабочую область. Меню «Слои» управляет картой;
переключатели над графиком — наблюдениями, восстановлением, исторической нормой и подсветкой событий.
Нажатие на событие приближает его период и открывает основания интерпретации.
Кнопка таблицы показывает точные значения, нажатие на дату или точку — подробности наблюдения.
Кнопка «Координаты» принимает широту и долготу, перемещает карту и ставит метку. Это позволяет быстро открыть район,
не разыскивая его вручную на подложке.

Во «Восстановлении» выбираются AOI и год из датасета. Валидатор проверяет текущий CSV;
метрика рядом относится к сохранённому CV-отчёту, а не к скрытым ответам test.
Доступность спутников, погоды и растров показана во вкладке «Данные» инспектора.

Если анализ содержит растровые слои, NDVI последнего снимка включается автоматически. В меню «Слои» можно выбрать
качество пикселей или вернуться к подложке. Слой пространственного отклонения недоступен, если выделенных зон нет.

Кнопка «Журнал» рядом с прогрессом открывает сообщения этапов с временем. Журнал обновляется каждые 2 секунды
и хранится на сервере; сетевое ожидание может идти без новых сообщений.

Sentinel-2 COG читаются ограниченным параллельным пулом. По умолчанию используются три потока; допустимый диапазон
`FLORASCOPE_SCENE_WORKERS` — от 1 до 4. Landsat обрабатывается последовательно, чтобы после requester-pays/403 не
повторять заведомо недоступный запрос для каждой сцены.

Обновление страницы не отменяет расчёт: статус последней задачи восстанавливается с сервера.
Выбранные поле, анализ, режим просмотра и параметры периода сохраняются в этом браузере.
Перезапуск самого API — другой случай: незавершённая задача помечается как прерванная, её нужно запустить заново.

## self-check

```bash
docker compose run --rm api python -m pytest -q /app/analytics/tests /app/backend/tests
docker compose run --rm api florascope-core inspect --dataset /data/input/train_dataset.csv
```

## batch / технический инференс

### вариант 1 — обучить и сразу сделать submission

```bash
docker compose run --rm api florascope-core competition \
  --train /data/input/train_dataset.csv \
  --input /data/input/private_features.csv \
  --artifacts /artifacts/competition_model \
  --output /data/output \
  --fast
```

Если входной файл называется иначе - просто подставьте его в `--input`.

Выход:

```text
data/output/submission.csv
data/output/report.json
data/output/analysis_points.csv
data/output/events.csv
artifacts/competition_model/
```

### вариант 2 — только инференс готовой модели

```bash
docker compose run --rm api florascope-core infer \
  --model /artifacts/competition_model \
  --input /data/input/private_features.csv \
  --output /data/output
```

Проверка submission:

```bash
docker compose run --rm api florascope-core validate-submission \
  --test /data/input/private_features.csv \
  --submission /data/output/submission.csv
```

Формат ровно такой:

```csv
anon_polygon_id,date,primary_ndvi_true
```

Natural gaps в submission не добавляем.

Актуальный тест после замены организаторами — `data/input/private_features.csv`: 49 190 строк, 20 AOI, 2323 synthetic
gaps. Старый `test_dataset.csv` оставлен для воспроизводимости прежних экспериментов; его submission больше не
отправляем. Подробности — [обновление датасета](docs/dataset_update.md).

## web-сценарий

В `Мониторинг`:

- рисуем Polygon кнопкой `✎` или импортируем GeoJSON;
- можно попробовать найти готовые `farmland/orchard/vineyard/meadow` через OSM Overpass;
- задаём сезон и число исторических лет;
- backend ищет Sentinel-2 и Landsat, подтягивает ERA5;
- после quality mask формируется временной ряд;
- UI показывает observed/restored/expected NDVI, negative events и spatial anomaly layers.

Landsat считается дополнительным источником: если публичный COG недоступен из-за requester-pays/сетевых ограничений,
анализ продолжает работать на Sentinel-2 + ERA5.

## внешние данные / API

Фиксируем явно, чтобы результат можно было воспроизвести:

- Earth Search STAC: `https://earth-search.aws.element84.com/v1`
- Sentinel-2 collection: `sentinel-2-c1-l2a`, fallback для отсутствующего AOI/сезона — `sentinel-2-l2a`
- Landsat collection: `landsat-c2-l2`
- погода: Open-Meteo Historical API, model `era5`
- контуры: OpenStreetMap Overpass API

Для Sentinel-2 используется L2A SCL pixel mask. `eo:cloud_cover` — только дешёвый prefilter сцен. Аналитическая сетка 20
м: red-edge/SWIR всё равно нативно 20 м, апскейл до 10 м новой информации не создаёт.

## модель

Начали с nearest/linear/Whittaker, потом добавили временной контекст, историю поля и сенсоры.

В данных нашли важную штуку: на всех известных train/test точках `primary_ndvi` совпадает с правилом:

```text
S2, если доступен → иначе Landsat → иначе MODIS
```

Поэтому финальная модель source-aware:

```text
общий LightGBM regressor
+
source classifier (S2/Landsat/MODIS)
+
3 source-conditioned regressors
→ blend
```

Быстрый CV (`seed=9901`), с независимой внутренней calibration для blend:

```text
linear               0.09291
Whittaker            0.08155
sensor median        0.08143
general LightGBM     0.06472
source-aware         0.06291
final blend          0.06218
source accuracy      92.999%
```

Seed 9901: GapScore 11.35 / 30. На трёх seeds RMSE 0.06419 ± 0.00324 (разброс между масками), не результат private
leaderboard. Подробнее и с исходными JSON: `research/report.md`, `research/results/`.

## как устроен CV

Outer validation mask создаётся первым и полностью исключается из context. Inner masks для обучения строятся только по
оставшимся известным точкам. Веса blend выбираются на отдельном внутреннем calibration mask; outer labels используются
только для оценки. Прежние 0.061986 получены с подбором весов по outer и сохранены как tuning result.

Кроме `primary_ndvi`, у target row зануляются и остальные динамические признаки. Иначе можно случайно подсмотреть
скрытые `s2_ndvi/landsat_ndvi/modis_ndvi` и получить слишком красивый CV.

## аномалии

Baseline из постановки оставили как есть:

```text
z >= -1       NORMAL
-2 <= z < -1  STRESSED
z < -2        CRITICAL
```

Но событие не создаём по одной плохой точке: нужен устойчивый блок. Норма строится по **другим годам** этого AOI. Для
объяснения дополнительно смотрим water index, ERA5 precipitation/temperature и отдельно ищем фенологический сдвиг формы
сезона.

Формулировки намеренно осторожные: «сигналы совместимы с дефицитом влаги», а не «мы диагностировали засуху».

## тесты

Основные риски покрыты тестами:

- private CSV может не содержать target;
- source-priority audit;
- exact synthetic mask;
- target dynamic values не протекают в features;
- smoothing;
- historical anomaly reference исключает текущий год;
- submission keys/NaN;
- SCL/raster helpers/STAC parsing;
- field repository и API CRUD.

## ограничения

- Реальный live-запуск зависит от сети и доступности внешних API.
- OSM далеко не везде содержит хорошие границы полей, поэтому draw + GeoJSON остаются основным fallback.
- Landsat публичные assets в некоторых окружениях требуют requester-pays. Он не является единственной опорой live
  pipeline.
- Confidence события — инженерная оценка качества evidence, не статистически откалиброванная вероятность причины.
- Foundation models смотрели, но в core не тащили: на одинаковом CV прирост ими пока не доказан.

## где что почитать

`research/report.md` — нормальный отчёт
`notes/data.md`, `notes/experiments.md`, `notes/related_work.md` — рабочие записи
`docs/architecture.md` — границы frontend/backend/analytics
`docs/api.md` — основные ручки
`docs/run_cross_platform.md` — Windows / Linux / macOS
`docs/reference/` — исходная постановка и критерии, по ним сверялись

## состав репозитория

В Git входят исходники, требования PDF, исследовательские результаты, organizer train, актуальный
`private_features.csv`, одна рабочая модель и текущие submission/графики. Старый `test_dataset.csv`
оставлен только для воспроизведения исходных экспериментов; отправлять результат по нему нельзя.

`.env`, кэши, зависимости, live-данные, резервные модели и промежуточные результаты исключены
через `.gitignore`. Производные данные и экспериментальный кандидат создаются командами из
[исследовательского отчёта](research/data_checks.md). Docker получает код; данные и модель
подключаются томами, а не копируются в образы.

## Связанные версии и лицензирование

[VegWatch](https://github.com/localzet-dev/vegwatch-dzz) — другая версия того же направления на отдельном стеке Workers/D1/R2. Общая тема — [florascope](https://github.com/topics/florascope). Репозитории не объединены автоматически: для переноса необходимы сопоставление API, схем данных, моделей и условий эксплуатации.

Исходный программный код распространяется по [AGPL-3.0-or-later](LICENSE). Опубликованные датасеты организаторов и обученные модели сохранены для воспроизведения экспериментов с разрешения владельца проекта. Их происхождение и границы применимости описаны в [заметке о данных](DATA_NOTICE.md).

Проверенные локальные команды: установка `analytics[dev]` и `backend[dev]` на Python 3.12, `python -m pytest -q analytics/tests backend/tests`, затем `npm ci`, `npm test` и `npm run build` в `frontend/`; `docker compose config --quiet` проверяет конфигурацию контейнеров. Эти проверки не подтверждают научную достоверность восстановления на новых территориях и не заменяют независимую валидацию модели.

Локальная конфигурация Compose по умолчанию публикует порты только на `127.0.0.1`: API исследовательского прототипа не имеет полноценного контроля доступа. Для доступа из локальной сети задайте `FLORASCOPE_BIND_ADDRESS` явно и настройте аутентификацию и ограничения на входе. CORS не заменяет аутентификацию. Изменение исходников не перезапускает существующую установку.

## Авторство

Сопровождающий собственных изменений: **Ivan Zorin (localzet)** — <creator@localzet.com> · https://www.localzet.com. Copyright © 2026 Localzet Group. Исходное авторство и лицензии сторонних компонентов сохраняются. См. [AUTHORS](.github/AUTHORS.md).
