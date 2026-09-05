# Проверка первой итерации — 2026-09-05

Исполнено на Linux x86_64 через Docker Compose:

| Проверка                                   | Результат                                           |
|--------------------------------------------|-----------------------------------------------------|
| `docker compose config`                    | Passed                                              |
| Config с amd64 fallback                    | Passed                                              |
| API + frontend Docker build                | Passed; `tsc -b` и Vite build внутри image          |
| analytics / backend tests                  | 26 + 4 = 30 passed                                  |
| Build/start                                | API healthy, web HTTP 200                           |
| Train inspect                              | 99 955 строк, 39 AOI, source priority 30 520/30 520 |
| Test inspect                               | 57 185 строк, 78 AOI, source priority 17 641/17 641 |
| CV seed 9901, inner calibration            | RMSE 0.06217523275333839; GapScore 11.35            |
| AOI вне обучения                           | 7 AOI, 813 targets, RMSE 0.05782079928477263        |
| Готовая новая модель → submission          | 3112 строк, validator true                          |
| Загрузка настоящего 8,2 MB CSV через nginx | HTTP 200                                            |
| MapLibre production worker                 | Включён в Vite bundle; проверка GeoJSON в браузере  |
| Browser benchmark                          | Метрика, VALID, 78 AOI и график видны               |
| Реальный Sentinel COG + ERA5               | Прочитаны; полный live статус в аудите              |

Команда повторной проверки: `scripts/check_release.sh` либо `scripts/check_release.ps1`. Оба сценария выполняют config →
build → tests → inspect → inference → validator. Bash дополнительно прошёл `sh -n`. PowerShell runtime, Windows, macOS и
native arm64 в этой среде не исполнялись.

Исходный score 0.061986 воспроизведён и сохранён как legacy tuning result: по outer выбирались веса blend. Независимый
результат находится в `research/results/cv_9901_nested.json`.

В pytest остаются предупреждения сторонних Starlette/Rasterio/Pillow о deprecated API; failures нет. Vite предупреждает
о размере bundle. Это ограничения, а не скрытые успешные тесты.

Полная сверка и оставшиеся P1/P2: [audit_iteration_1.md](audit_iteration_1.md).

Финальная повторная API build выполнена через временный network/proxy override данного Linux-хоста после медленного PyPI
и transient Debian 502. Исходники для этого не менялись; base build ранее прошёл. Все 30 тестов, inference и validator
повторены именно в финальном image.
