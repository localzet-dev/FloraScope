# live eo

сначала хотели сделать вообще всё: postgis, worker отдельным контейнером, несколько tile сервисов. потом стало понятно,
что для одного ноута это больше головной боли, чем пользы.

сейчас:

- web отдельно;
- api отдельно;
- job executor внутри api;
- sqlite для metadata/jobs;
- geotiff/model/csv файлами.

Sentinel основной live source. Landsat optional: requester-pays иногда мешает, не валим из-за него весь job.

eo:cloud_cover только prefilter. потом всё равно SCL/QA внутри polygon.

20м намеренно из-за red-edge/swir.

TODO если останется время:

- cache STAC search;
- аккуратнее показывать source coverage в UI;
- reusable local manifest provider для совсем офлайн demo.

Реальный прогон выявил два разных затыка: Docker не наследовал proxy хоста; потом для AOI 39E/45N C1 за лето 2022 вернул
0 сцен, legacy L2A — 24. Добавили optional proxy config и fallback коллекции. Scale/offset берём из конкретного asset.

Integer GeoTIFF с nodata раньше падал на fill NaN. Теперь float до fill, SCL отдельно. Настоящий COG прочитан, не только
локальная fixture. Landsat реально ответил Requester Pays — доступ не изображаем. После access denied не дёргаем каждый
следующий COG.
