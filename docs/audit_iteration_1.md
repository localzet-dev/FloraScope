# Аудит первой итерации

Источник требований: `reference/task_statement.pdf`, все 19 страниц; `reference/judging_criteria.pdf`, все критерии.
Проверка 2026-09-05. Это рабочая копия без `.git`, поэтому чистый git checkout здесь не проверен. Наличие реализации не
означает подтверждённое качество.

| Критерий                   | Баллы | Реализация и фактический пробел до исправлений                                                                                                                                                                                                                                                                                                              |
|----------------------------|------:|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Метрика                    |    30 | RMSE/GapScore и synthetic-only submission реализованы. Outer исключён из training context, но веса blend выбираются по outer labels: результат 0.061986 является tuning score, не независимой оценкой финального blend.                                                                                                                                     |
| Ясность презентации        |     5 | Есть demo.md и research-экран, готовых слайдов и скриншотов нет.                                                                                                                                                                                                                                                                                            |
| Выступление                |     5 | Есть сценарий; навыки выступления и ответы команды кодом не проверяются.                                                                                                                                                                                                                                                                                    |
| Демонстрация решения       |     5 | Две точки входа существуют. Реальная Compose build упала: MapPane.tsx, неверный тип layer click event.                                                                                                                                                                                                                                                      |
| Детекция аномалий          |     7 | Historical reference без текущего года, z thresholds, persistence, batch water/weather, phenology и live spatial. Batch склеивает отрицательные точки через нормальные; NaN reference объявляется NORMAL. Live confidence зависит от интерполированных точек; spectral evidence не используется в temporal events. Phenology batch предполагает шаг 5 дней. |
| Управление полигонами      |     5 | CRUD, Polygon/MultiPolygon, draw, GeoJSON, OSM ways реализованы. Нет автоматического позиционирования на выбранное поле; OSM-кандидаты показаны списком без контуров на карте; импортирует только первый Feature.                                                                                                                                           |
| Автосбор и подготовка      |     5 | Реальные STAC/COG/ERA5/Overpass клиенты, partial errors предусмотрены. Integer masked raster → NaN падает. STAC только первая страница; выбор сцен может обрезать сезон. Landsat AOI allocation без ограничения.                                                                                                                                            |
| Множественные регионы      |     5 | Координаты задаёт пользователь; ID не feature. Нет group-held-out эксперимента. Начальный центр карты не ограничивает API, но UX новых территорий слабый.                                                                                                                                                                                                   |
| Дополнительные идеи        |     5 | Source-aware recovery, phenology, spatial layers, confidence реализованы; нужны проверки нетривиальных случаев и честной поддержки evidence.                                                                                                                                                                                                                |
| Baseline и отправная точка |     5 | Linear/Whittaker/sensor/climatology и ограничения описаны. Точный baseline PDF (среднее соседей) отдельно не измерен; linear считается по номеру строки.                                                                                                                                                                                                    |
| Эксперименты и сравнения   |     5 | Raw JSON, seed и параметры есть. Нет independent blend evaluation, held-out AOI и gap-length breakdown; результаты DL не заявлены.                                                                                                                                                                                                                          |
| Код и комментарии          |     3 | Границы сохранены, понятные Python/TS модули, русские пояснения. Дублируются batch/live event algorithms и выбор test path. Геометрия/площадь в repository смешана с persistence.                                                                                                                                                                           |
| Документация и запуск      |     5 | README, Compose, Bash/PowerShell есть. Native arch, named SQLite volume, отдельный nginx соблюдены. Реальная web build не проходит; npm lock отсутствует. Windows/macOS ещё не исполнены.                                                                                                                                                                   |
| UX                         |     5 | Карта, observed/restored/expected, события, история, jobs. Завершённый live job не открывает результат; старый analysis остаётся при выборе другого поля; upload CSV превышает default nginx 1 MB.                                                                                                                                                          |
| Дополнительная ценность    |     5 | Сохранение анализов, raster layers, batch/API полезны. Нужен сохранённый реальный live результат с provenance; offline fixture не доказательство внешнего acquisition.                                                                                                                                                                                      |

## Приоритеты

P0 — блокирует запуск, доверие к метрике или базовую корректность:

- Исправить TS build и проверить build/start через Compose.
- Отделить calibration blend от outer evaluation, сохранить исходный seed/masking и старые raw результаты как tuning;
  повторить benchmark и inference/validator.
- Исправить integer raster/nodata, подтвердить реальным COG и регрессионным тестом.
- Убрать ложную persistence/уверенность от восстановленных точек, UNKNOWN при отсутствии reference; проверить phenology
  на реальных днях и отсутствие сдвига у нормальной кривой.
- Устранить обрезание STAC discovery и защитить размеры Landsat grid.
- Разрешить organizer CSV через nginx, не уничтожать рабочий датасет невалидным upload; единый выбор private/test.

P1 — доказательства качества и завершение продукта:

- Group-held-out AOI diagnostic отдельно от основного CV; gap-length/source breakdown.
- Реальный polygon → acquisition → trajectory → events → API/UI прогон с источниками и ограничениями. Если внешний
  сервис недоступен — явно записать фактический отказ, не считать fixture live-проверкой.
- Нормализованные spectral/weather evidence для live, spatial reference по близкой фазе и независимым годам.
- Выбор/позиционирование поля и согласованный analysis, автоматическое открытие готового результата, события на графике,
  confidence и coverage в UI.
- Lockfile npm, Compose build в CI, native arm64/Windows/macOS smoke на соответствующих хостах.
- 2–3 проверяемых anomaly cases, слайды и репетиция.

P2 — улучшения после надёжного основного пути:

- OSM relations/preview, несколько GeoJSON features, поиск региона.
- Cache/manifests EO, richer gap ablations, offline просмотр сохранённых реальных результатов.
- Общие helpers event logic только после тестов, без переписывания core и новых сервисов.

## Архитектура

analytics не импортирует backend/FastAPI/SQLite/frontend; backend вызывает analytics через Python package; frontend
получает REST/tiles и не пересчитывает anomaly logic. Docker содержит ровно api/web. Эти границы сохраняем. Небольшую
геометрию в repository и дублирование batch/live отмечаем как локальный долг, не повод переделывать архитектуру.

## Проверки

Первый `docker compose config --quiet` прошёл. Первый `docker compose build` упал на TS2339 в MapPane.tsx:100.
Результаты исправлений и исполненных проверок будут добавлены ниже; старые release claims не считаются текущим прогоном.

## Исправления и проверка после аудита

- **Docker/TS:** layer click использует выведенный MapLibre type; добавлен необходимый Rasterio `libexpat1`; npm
  lockfile и `npm ci`. Compose build действительно проходит. MapLibre 6 worker явно включён в Vite bundle
  (`?worker&url`): без него OSM виден, а GeoJSON не рисуется. CI и оба release scripts теперь выполняют Docker build.
- **CV:** inner calibration отделена от outer, исходный mask и seeds сохранены. Исходный результат воспроизвёлся точно;
  новая оценка 0.06217523275333839 / 11.35. Тест подменяет outer labels и проверяет неизменность training/calibration
  features и labels.
- **Submission:** inference сам вызывает validator; проверяется точная схема, keys, duplicates, NaN/inf, missing/extra
  rows. Новая production-модель обучена, выдала 3112 валидных строк; старые artifacts/output сохранены отдельно.
- **Raster:** float conversion до NaN fill, nodata вне footprint, finite NDVI входит в quality fraction, SCL/QA
  сохраняются pixel masks. Ограничен Landsat grid; morphology не заполняет nodata как доказанную площадь. Реальный
  Sentinel COG прочитан: `S2B_T37TDK_20240728T082249_L2A`, 560 ячеек на сетке 20 м, valid fraction 0.680357.
- **Discovery:** STAC pagination и ограничение бюджета по всему временному интервалу. Выбор более чистых сцен не может
  последовательными заменами схлопнуть весь сезон в одну дату. GET выбран как стандартный STAC интерфейс; сеть требует
  отдельной проверки proxy, это не свойство STAC POST.
- **Events:** нормальная/неизвестная точка разрывает negative block, нет NORMAL без reference, восстановленные точки не
  считаются независимыми наблюдениями. Phenology использует календарные дни, одинаковый интервал сравнения и выигрыш над
  нулевым лагом. Live confidence учитывает реальную поддержку, историю и качество; NDMI/ERA5 evidence сравниваются с
  историей. Осадки за 30 дней требуют всех 30 календарных значений.
- **API:** nginx пропускает реальные organizer CSV; загрузка 8,2 МБ через web endpoint прошла. Невалидная загрузка не
  удаляет предыдущий dataset. Private features имеют единый приоритет во всех API entrypoints. Queued/running jobs после
  рестарта получают INTERRUPTED.
- **UX:** выбранное поле помещается в viewport; результат согласован с выбранным полем и подхватывается из истории; raw
  sources заменены coverage/ошибками; confidence виден; события выделены на live timeline. Проверен браузер: 0.0622,
  11.35, VALID, 78 AOI, график observed/restored/climatology.
- **Перенос:** 7 AOI целиком вне training/context/calibration, RMSE 0.05782079928477263 по 813 targets. Это отдельная
  диагностика, не улучшение основной метрики; на long-gap группе только 13 targets. Код и raw сохранены в research.

## Что остаётся

- Полноценная оценка uncertainty; три seeds уже выполнены: mean RMSE 0.0641948, std 0.0032441. Исходный seed исторически
  участвовал в выборе архитектуры.
- Больше проверенных реальных регионов и нетривиальных anomaly cases с осторожной интерпретацией. Confidence всё ещё
  инженерная оценка, не probability причины.
- Spatial reference следует дополнительно ограничить по близости фазы и независимым годам; temporal и spatial evidence
  имеют разную поддержку.
- OSM-кандидаты на карте, multi-feature GeoJSON, поиск региона и фильтр сезона batch-графика.
- Windows, macOS и native arm64 должны быть исполнены на соответствующих хостах. Проверка config amd64 fallback не
  означает проверку arm64 runtime.
- Слайды и репетиция защиты. Два organizer кейса (negative deviation и phenology shift) уже разобраны с графиками в
  `research/report.md`; это не размеченная оценка detector.

Сеть: на этом Linux-хосте внешний доступ идёт через loopback proxy. Base Docker не наследовал его, поэтому первая
STAC-страница могла отвечать, а следующая — зависать. Добавлены необязательные FLORASCOPE_HTTP_PROXY/HTTPS_PROXY и
объяснение доступности endpoint из контейнера. Отдельные реальные ERA5 и COG проверки прошли. Статус полного live job
зафиксирован отдельно ниже; fixture не выдаётся за live.

## Итог реального live-прогона

`live-7bca6977ca`: polygon → STAC → COG/SCL → 12 пригодных observations → temporal analysis → сохранённый API result
выполнен. Период июль–август 2025, AOI 39E/45N, история 2023–2024. Текущих точек 2, исторических 10; negative events
нет. Это не доказательство чувствительности detector и не повод создавать искусственное событие.

Во время прогона proxy перестал отвечать. Погода и spatial layers отсутствуют, ошибки сохранены. Поэтому **полный
live-показ с ERA5 и raster layers остаётся P1**; отдельные COG/ERA5 запросы и локальный интеграционный raster test
проходят. Temporal result повторно обработан из сохранённых реальных observations после исправления reference support,
без повторного acquisition.

Для отсутствующего C1 AOI/сезона добавлен fallback `sentinel-2-l2a`: реальный поиск за лето 2022 вернул там 24 сцены
против 0 C1. Тест fallback проходит. Больше данных не заменяет pixel quality mask.

Финальная проверка: 30 tests passed в собранном image, повторные inference/validator — true, 3112 строк; API healthy.
Повторная API сборка потребовала временного сетевого override для loopback proxy этого хоста; Dockerfile и production
Compose сохраняют переносимый контракт. Официальная схема worker: https://maplibre.org/maplibre-gl-js/docs/.
