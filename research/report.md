# research report

Короткая версия того, что реально делали. Raw результаты лежат рядом в `results/`.

## задача / протокол

В `private_features` synthetic row скрывает `primary_ndvi` и динамические признаки этой даты. Поэтому обычный row-wise
regression тут не работает — надо восстанавливать точку из временного/исторического контекста.

Метрика: RMSE по synthetic gaps, потом `GapScore = round(30 * max(0, 1 - RMSE / 0.10), 2)`.

Для локальной проверки сделали такой же ~15% mask. Outer mask создаём первым и больше нигде не используем как training
label/context. Inner masks создают обучающие примеры только из remaining known rows.

## EDA, что реально повлияло на решение

Train: 99 955 строк, 39 AOI, 2010–2024, 30 520 известных `primary_ndvi`.

Test: 57 185 строк, 78 AOI, 2010–2025, 17 641 известных `primary_ndvi`, 3 112 synthetic gaps.

39 test AOI есть в train, ещё 39 — новые. Поэтому `anon_polygon_id` как categorical feature не используем.

Самое полезное наблюдение: `primary_ndvi` на **100% известных точек** совпал с приоритетом S2 → Landsat → MODIS:

- train: 30 520 / 30 520;
- test known: 17 641 / 17 641.

Отсюда появилась source-aware ветка.

## baseline

Первое, что попробовали — простые временные методы. Они полезны как точка отсчёта и fallback, даже если финально
проигрывают ML.

На фиксированном outer split seed=9901:

| метод                        |    RMSE |
|------------------------------|--------:|
| linear interpolation         | 0.09291 |
| Whittaker                    | 0.08155 |
| median sensor interpolation  | 0.08143 |
| climatology + local residual | 0.14850 |
| AOI climatology              | 0.19130 |

Linear понятно ломается на длинных дырках. Whittaker лучше держит форму сезона. Одна climatology без текущего season
context оказалась слабой — оставили её признаком, не основным predictor.

## финальная гипотеза и исходный tuning result

General LightGBM уже умеет выбирать между локальной интерполяцией, сглаживанием, сенсорами и seasonal context.

Потом добавили:

1. classifier скрытого source: S2/Landsat/MODIS;
2. отдельный regressor для каждого source;
3. blend general + source-conditioned prediction.

Исходный результат на том же split. В первой проверке обнаружено: веса blend выбирались по этому же outer split, поэтому
финальная строка ниже является tuning result:

| вариант                |        RMSE |
|------------------------|------------:|
| general LightGBM       |     0.06472 |
| source-aware branch    |     0.06291 |
| calibrated final blend | **0.06199** |

Source classifier accuracy: **92.999%**.

Breakdown финального prediction:

| source  | rows |    RMSE |
|---------|-----:|--------:|
| S2      | 1693 | 0.06707 |
| Landsat | 2008 | 0.05739 |
| MODIS   |  870 | 0.06191 |

Это не leaderboard result — локальная имитация private gaps. Исходный blend дополнительно подбирался по outer labels;
независимый пересчёт ниже. Используем для выбора архитектуры, а не как обещание балла.

## что не дало смысла / не тащили

- Одна climatology слишком грубая.
- Просто усреднять sensor estimates хуже source-aware выбора.
- Foundation models изучали как related work, но core не усложняли без честного прироста на том же CV.
- Forecasting-first модели не очень совпадают с постановкой: у gap есть контекст и до, и после точки.

## anomaly layer

Официальный z-score — baseline:

```text
z >= -1       штатно
-2 <= z < -1  угнетение
z < -2        критическая аномалия
```

Норму считаем по **другим сезонам AOI**, текущий год из reference исключён. Одиночная плохая точка событием не
считается — нужен устойчивый блок.

Дополнительно:

- water index;
- ERA5 precipitation / temperature;
- phenology shift по сходству формы сезонной кривой;
- в live режиме — spatial z-score компоненты на Sentinel raster.

Причины формулируем как гипотезу evidence: «совместимо с дефицитом влаги», а не как агрономический диагноз.

## воспроизводимость

Все версии зависимостей pinned в `analytics/pyproject.toml`, `backend/pyproject.toml`, `frontend/package.json`.

CV:

```bash
docker compose run --rm api florascope-core benchmark \
  --train /data/input/train_dataset.csv --fast
```

Production + inference:

```bash
docker compose run --rm api florascope-core competition \
  --train /data/input/train_dataset.csv \
  --input /data/input/test_dataset.csv \
  --artifacts /artifacts/competition_model \
  --output /data/output --fast
```

Raw audit/CV: `research/results/*.json`.

## зафиксированные параметры release

Чтобы потом не искать их по коду:

```text
synthetic mask fraction   0.15
CV seed                   9901
production mask seeds     15001, 15002   (fast profile)

LGBM regressor
  n_estimators            320
  learning_rate           0.04
  num_leaves              55
  min_child_samples       12
  subsample               0.90
  colsample_bytree        0.90
  reg_lambda              1.20
  reg_alpha               0.03

source classifier
  n_estimators            220
  learning_rate           0.04
  num_leaves              47

Whittaker lambda          1000
Sentinel scene gap        7 days
Landsat scene gap         12 days
live grid                 20 m
scene cloud prefilter     35% default
live AOI safety limit     300000 cells
```

Все числа продублированы в коде; если меняем — сначала эксперимент, потом обновляем эту заметку и raw result.

## Перепроверка 2026-09-05

Исходный fast benchmark воспроизведён в Docker: 0.06198617140699296, без расхождения с `results/cv_9901.json`.

Исправление касается только выбора ensemble weights: внутри remaining known выделяется calibration mask (seed 9951); её
labels и dynamic context исключены из обучения calibration-модели. После выбора весов обучаем оценочную модель на
прежних inner masks (10001/10002) с исключённым outer seed 9901. Outer fraction и алгоритм masking не менялись. Это
проверяется тестом: изменение outer labels не меняет training examples, calibration features и calibration labels.

Реальный результат: `results/cv_9901_nested.json`.

| Вариант                        |                RMSE |
|--------------------------------|--------------------:|
| General LightGBM               | 0.06472451852820371 |
| Source-aware                   | 0.06290834755963909 |
| Blend с внутренней calibration | 0.06217523275333839 |

GapScore 11.35; 4571 outer targets. Это один split и локальная оценка, не гарантия private score. Ранее этот seed уже
использовался для выбора архитектуры, так что полностью нетронутым holdout его также называть нельзя. Group-held-out AOI
проверен отдельно ниже; три seeds проверены ниже.

Обучена новая production-модель с той же fast-конфигурацией и независимо выбранными весами. Получено 3112 строк
submission, ключи и finite predictions проверены validator. Исходная модель сохранена в
`artifacts/competition_model_legacy`, рабочая модель — `artifacts/competition_model`.

Live-проверки и ограничения первой итерации: `docs/audit_iteration_1.md`. После настройки сетевого доступа выполнен
полный live-анализ нового полигона: 49 Sentinel-2 кандидатов, 47 пригодных наблюдений, ERA5 и выходные raster layers.
Последовательный запуск занял 1079.7 с. Ограниченный пул из трёх чтений затем проверен на реальных COG: 20.7 с против
36.1 с последовательно (1.74x на этом наборе; это измерение загрузки, не гарантия общего ускорения).
Новых результатов foundation-model экспериментов нет.

## Перенос на AOI вне обучения

Скрипт `research/unseen_aoi.py`, raw `results/unseen_aoi_9901.json`. Seed 9901 детерминированно выделяет 7 из 39 AOI.
Все их строки исключены из обучения и calibration, включая aggregate context. На новых AOI для inference остаются
известные наблюдения, как в private features; маскируются 15% известных точек тем же алгоритмом. Внутренняя calibration
выполняется только на 32 обучающих AOI.

Результат: **RMSE 0.05782079928477263**, 813 targets. Это диагностическая выборка другого состава, поэтому меньшая
ошибка не является улучшением относительно основного CV.

| Расстояние между видимыми соседями | Targets |    RMSE |
|------------------------------------|--------:|--------:|
| ≤10 дней                           |     539 | 0.05410 |
| 11–30 дней                         |     230 | 0.06448 |
| >30 дней                           |      13 | 0.04899 |
| Только один сосед                  |      31 | 0.07028 |

В группе >30 дней всего 13 точек — заключать, что длинные gaps легче, нельзя. Один сосед остаётся проблемным случаем.

Повторить из корня в Bash или PowerShell с Docker:

```text
docker compose run --rm -v "${PWD}/research:/research:ro" api python /research/unseen_aoi.py --train /data/input/train_dataset.csv --output /data/output/unseen_aoi_9901.json
```

Скрипт учит временные модели отдельно и не заменяет production artifacts.

## Устойчивость к synthetic mask

Реальный `benchmark --fast --three-seeds`, raw `results/cv_three_seeds_nested.json`. Каждый split подбирает blend только
на своей внутренней calibration.

| Seed  |                RMSE |
|-------|--------------------:|
| 9901  | 0.06217523275333839 |
| 10039 | 0.06877210243024894 |
| 10177 | 0.06163713184801601 |

Среднее **0.06419482234386777**, std между тремя масками **0.0032440723263580623**. Это не доверительный интервал и не
три независимых региона. Seed 10039 заметно сложнее: оценивать готовность только по 9901 было бы оптимистично.
Production weights остаются от заранее указанного 9901; лучший seed по этим результатам не выбирали.

## Проверка live acquisition

Реальный AOI `[39.0, 45.0, 39.005, 45.005]`, июль–август 2025, история 2023–2024: 12 пригодных observations (2 текущих,
10 исторических). Сохранён `live-7bca6977ca`. Во время acquisition proxy перестал отвечать: ERA5 и spatial layer
недоступны, Landsat вернул Requester Pays. Temporal workflow завершился, negative events не найдено. Это пример
частичной доступности, не полноценный показ всех live-возможностей.

После исправления поддержки исторической нормы результат пересчитан из тех же сохранённых observations; повторный
acquisition не заявляется. Manifest сохраняет сцену, asset URL/scale/offset, геометрию, период, quality и ошибки.
Отдельный реальный COG и отдельный ERA5 запрос успешно проверены ранее.

Обнаружен неполный C1 архив для AOI/лета 2022: 0 сцен против 24 в legacy `sentinel-2-l2a`. Добавлен fallback при пустом
C1 поиске. Это отдельная коллекция того же Earth Search, с собственными metadata scale/offset. Реальные новые измерения
аномалий из неё пока не заявляются.

## Два случая для разбора

Графики построены из фактических organizer inference outputs, без ручной разметки причин. Скрипт
`research/anomaly_cases.py`
выбирает самый длинный negative event и первый phenology event; это иллюстрации поведения, не оценка precision/recall.

- [AOI-0073, 2020](results/anomaly_case_1.png): отрицательное отклонение 2 июля — 23 сентября, min z −3.20, 33 настоящих
  наблюдения внутри события. Погодные отклонения небольшие, water z положительный: оснований называть причиной засуху
  нет. Ранний максимум и резкое снижение также совместимы со сменой культуры/уборкой; без ground truth остаётся описание
  изменения траектории.
- [AOI-0001, 2012](results/anomaly_case_2.png): кандидат на раннюю фазу, лучший lag −15 дней, shape correlation 0.969
  против 0.918 без сдвига. Это граница проверяемого диапазона ±15 дней, а не точная дата агрономического события. Важны
  форма и календарная поддержка, не только отрицательный z. HIGH — инженерная категория, не вероятность причины.

Параметры событий сохранены в `results/anomaly_cases.json`. В окружении с pandas и matplotlib 3.10.6:
`python research/anomaly_cases.py --input data/output --output research/results`.

## Прогоны после обновления organizer test

[Отдельный отчёт](data_checks.md): парное удаление organizer climatology, переобучение с новой схемой, скрытие видимых
observations на 20 новых test AOI и независимый MODIS-only stress test из ORNL DAAC. Эти результаты не заменяют старые
raw CV и не смешиваются в одну метрику.
