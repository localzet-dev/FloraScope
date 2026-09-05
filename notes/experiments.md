# experiments

цифры ниже: outer mask seed 9901, fast profile. raw json в `research/results/cv_9901.json`.

## linear

0.09291

самый тупой baseline, зато сразу видно масштаб задачи. на длинной дырке закономерно плывёт.

## whittaker

0.08155

заметно лучше. оставили и baseline, и feature.

## sensor median

0.08143

почти whittaker. просто усреднять источники недостаточно.

## climatology

aoi 0.19130, corrected 0.14850.

сама по себе слабая. зато historical context полезен модели.

## general lgbm

0.06472

первый реально сильный вариант. 100+ обычных temporal/context features, без polygon id.

## source-aware

classifier source ~93% accuracy. source-conditioned prediction 0.06291. blend 0.06199.

оставляем. идея норм объясняется через найденное правило primary source, а не "ещё один ансамбль потому что можем".

## потом

- gap-length breakdown было бы полезно добить;
- отдельный unseen-aoi diagnostic тоже;
- сложный DL только если останется время и тот же split реально улучшится.

## перепроверка

потыкали настоящий Docker: старые 0.061986 повторились точно. Но blend подбирался по outer — это tuning score. Вынесли
подбор во внутреннюю calibration, тот же outer теперь 0.062175 (11.35 балла локально). General/source ветки не
поменялись. Raw: `research/results/cv_9901_nested.json`.

Ещё нашли ложную persistence через нормальные точки и confidence от интерполяции. Починили, phenology теперь считает
календарные дни и требует выигрыш относительно нулевого лага. Это тесты механики, не подтверждение агрономических
причин.

Held-out AOI тоже добили: 7 полей совсем вне train/context/calibration, 813 targets, RMSE 0.057821. Не сравниваем как
«стало лучше»: набор другой. Односторонние gaps 0.07028, длинных двусторонних всего 13 — выводы по ним пока не делаем.

Три маски: 9901 0.06218, 10039 0.06877, 10177 0.06164. Среднее 0.06419, std 0.00324. 10039 неприятнее; лучший seed не
выбираем, production weights оставили как было.

05.09, новый test: погоняли known observations на 20 AOI, которых нет в train. Скрывали строки целиком; 1970 targets на
маску. Старая модель в среднем 0.07345, linear 0.09932. Не secret-test score, но уже проверка переноса. Из ORNL реально
скачали 3 MODIS ряда (483 даты). На maize норм, на GLEES и South Denver linear лучше. MODIS-only на чужом масштабе
нельзя рекламировать как универсальный predictor. Raw и график в research/data_checks.md. Два LightGBM прогона
одновременно на 4 физических ядрах сильно тормозят — лучше по одному.

Парный schema ablation закончен: 0.064195 original / 0.064475 missing / 0.064219 retrained. Новый production-кандидат на
known new-test: 0.073231 vs 0.073449, крошечный выигрыш. Основную модель и submit оставили как были.
