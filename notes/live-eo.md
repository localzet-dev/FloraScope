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

05.09, таймауты каталога на новом AOI: root endpoint отвечал, но GET поиска и следующая POST-страница
напрямую зависали. Через уже настроенный на машине proxy полный GET search за 2023 прошёл: S2 C1 13,
S2 legacy 13, Landsat 21 сцен после cloud prefilter, 2.2–2.5 с. Локальный .env подключает proxy через
host.docker.internal; адрес машины не переносили в default config. Метод STAC не меняли: проблема не в GET как таковом.
При отсутствии сцен из-за ошибок каталога больше не пишем, что их отсеяла pixel quality mask. 34 tests passed.
После proxy каталог ожил, но Rasterio долго искал соседние файлы COG. С GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR
реальная сцена S2 2023-03-01 прочиталась вместе с маской за 15.2 с (включая поиск): grid 46×151,
valid_fraction 0.980345, NDVI 0.202337. Добавили настройку в Compose: используемые COG самодостаточны.

05.09, полный повтор для нового полигона 47N: сезон 2026 + 3 года истории завершился за 1079.7 с.
S2: 49 кандидатов, 47 пригодных; 16 текущих + 31 историческое наблюдение. ERA5 доступна.
Landsat нашёл 34 кандидата, первый COG вернул requester-pays, остальные не дёргали. Получили 40 точек ряда,
1 temporal event, слои ndvi/zscore/quality. Это последовательный запуск до включения пула.

Для следующих запусков S2 COG читаем пулом из 3 потоков (настройка 1–4). На трёх реальных сценах этого AOI:
20.7 с параллельно против 36.1 с последовательно, ускорение 1.74x. Все три сцены прошли чтение pixel mask.
Локальный fixture подтверждает ровно три одновременных чтения и полный pipeline; Landsat оставили последовательным.
