# Независимые MODIS данные

Реально скачаны через [ORNL DAAC TESViS REST API](https://modis.ornl.gov/data/modis_webservice.html), продукт MOD13Q1,
band `250m_16_days_NDVI`, 2018–2024. URL и SHA256 каждого ответа — `manifest.json`. Повторное получение:
`python research/download_external_modis.py`; существующие raw ответы не перезаписываются.

Сайты:

- [US-Ne1](https://ameriflux.lbl.gov/sites/siteinfo/US-Ne1): Mead, irrigated continuous maize.
- [US-GLE](https://modis.ornl.gov/cgi-bin/sites/site/?network=AMERIFLUX&network_siteid=US-GLE&product=MOD13Q1): Wyoming
  GLEES.
- [US-SDU](https://modis.ornl.gov/cgi-bin/sites/site/?network=AMERIFLUX&network_siteid=US-SDU&product=MOD13Q1): Colorado
  South Denver.

Это средние по окнам из 1089 MODIS pixels, а не точечные flux measurements и не границы конкретных полей. MOD13Q1 —
16-дневные композиты, номинально 250 м. API statistics уже масштабированы в NDVI; использован `value_mean`, оставлены
даты с `pixels_pass_rel >= 80`. Порог 80% — фиксированный выбор для stress test, не критерий организаторов.
Погода/Sentinel/Landsat отсутствуют, crop_type=UNKNOWN; реальные названия культур не выдумываются.

`external_modis_check.py` скрывает 15% известных точек по тому же helper/трём seeds, целиком исключая target row из
dynamic context. Production-модель заморожена. Из-за частоты/масштаба/малой выборки это отдельная проверка переноса, не
organizer CV. Измерения не добавлялись в обучение. Дополнительно temporal core обработал 2024 год с историей 2018–2023;
наличие события не подтверждает его агрономическую причину.

Атрибуция: ORNL DAAC. 2018. TESViS RESTful Web Service, DOI: 10.3334/ORNLDAAC/1600. MOD13Q1: Didan, K. 2021. MODIS/Terra
Vegetation Indices 16-Day L3 Global 250m SIN Grid V061, DOI: 10.5067/MODIS/MOD13Q1.061.
