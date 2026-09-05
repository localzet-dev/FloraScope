# на почитать

## SAITS

https://github.com/WenjieDu/SAITS

time-series imputation, self-attention. по смыслу ближе большинства. полезная мысль: маска/паттерн пропусков — часть
постановки, а не просто NaN после предобработки. в core не тащим: сначала надо обыграть дешёвый tabular/temporal
baseline на том же CV.

## MOMENT

https://github.com/moment-timeseries-foundation-model/moment

универсальный foundation model для time series, есть reconstruction. посмотрели как challenger. для нашего объёма +
нерегулярных acquisition dates пока пушка по воробьям.

## SITS-BERT

https://github.com/linlei1214/SITS-BERT

интереснее тем, что именно satellite time series и self-supervised corrupted observations. сама pretrained задача у них
classification-oriented, но идея bidirectional masked context хорошо совпадает с gap recovery.

## Presto

https://github.com/nasaharvest/presto

pretrained transformer под remote sensing timeseries. для live EO интереснее, чем для competition CSV: в csv уже
потеряна большая часть spatial/spectral структуры.

## phenofit

https://github.com/eco-hydro/phenofit

phenology + curve fitting, есть Whittaker. отсюда ещё раз убедились, что smoothing — нормальная отправная точка, а не
"слишком простой" метод.

## FORCE

https://github.com/davidfrantz/force

production EO pipeline / data cubes / Landsat + Sentinel. код себе не тащили, смотрели скорее на разделение ingestion →
quality → time series → products.

## sits

https://github.com/e-sensing/sits

ещё один пример нормального satellite time-series workflow и multisource data cubes.

итог: полезнее всего оказались не готовые веса, а общие паттерны — masked reconstruction, quality-aware ingestion,
seasonal fitting, multisource separation.
