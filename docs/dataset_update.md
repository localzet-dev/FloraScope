# Замена теста организаторами

2026-09-05 получен `test_features (1).csv` с уведомлением, что прежние submissions недействительны.

- Train из полученного ZIP побайтово совпадает с `train_dataset.csv` (99 955 строк, 39 AOI).
- Прежний тест: 57 185 строк, 78 AOI, 3112 synthetic gaps.
- Новый тест: 49 190 строк, 20 AOI, 2323 synthetic gaps; все 20 AOI отсутствуют в train.
- Новый тест убирает `ndvi_climatology_mean` и `ndvi_climatology_std`. На synthetic rows target/sensors/weather пусты.
- Source priority Sentinel-2 → Landsat → MODIS подтверждён на всех 13 164 известных observations нового теста.

Актуальный вход — `data/input/private_features.csv` (локальная копия `test_features_updated.csv` не включается в Git). SHA256:
`f7ba087818175ea644fc9fe652c6a3874b5bfcde7df197d3e7541cb95876f855`.

Готовая production-модель выполнила inference без изменения кода; отсутствующие признаки выравниваются как NaN.
`data/output/submission.csv` содержит новый результат, validator проверен именно против нового теста. Прежний submission
и его analysis outputs сохранены локально в `data/output/previous_test_submission/`, исключены из Git и не предназначены для отправки.

Это проверка формата и выполнения, не оценка RMSE: скрытых ответов нет. Прежние CV и графики остаются результатами
исходного validation setup; отсутствие organizer climatology в новом test проверено отдельно: средний RMSE на train CV
0.064475 против исходных 0.064195. Полный отчёт — `research/data_checks.md`. Не следует восстанавливать удалённые
столбцы из старого теста: новый файл является актуальным контрактом.
