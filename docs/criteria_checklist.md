# Сверка с требованиями

Полная таблица всех критериев, приоритеты и результаты первой проверки: [audit_iteration_1.md](audit_iteration_1.md).

Основные доказательства:

- Основной CV с независимым подбором blend: `research/results/cv_9901_nested.json`.
- AOI вне обучения и gap-span breakdown: `research/results/unseen_aoi_9901.json`.
- Воспроизводимый запуск: `scripts/check_release.sh` / `scripts/check_release.ps1`.
- Текущие исполненные проверки: [release_check.md](release_check.md).
- Источники требований: оба PDF в `reference/`.

Реализация функции, тест на fixture и успешный реальный внешний запрос — разные уровни доказательства. В аудите они
отмечены отдельно. Презентация и навыки выступления ещё не проверены.
