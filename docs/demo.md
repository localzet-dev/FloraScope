# demo на защите

не пытаться показывать всё.

1. **30 сек — задача**: есть дырки в NDVI и есть вопрос "это реально угнетение или просто шум/облако?".
2. **1 мин — benchmark**: открыть model/benchmark, показать baseline → source-aware → RMSE, выбрать AOI, ткнуть restored
   points + anomaly period.
3. **2 мин — live**: сохранённое поле → карта → trajectory → zscore layer → event explanation. Если интернет норм —
   можно отдельно показать draw + запуск нового job, но не ждать его в прямом эфире.
4. **30 сек — research**: source priority 100% known rows, почему не тащили DL ради DL, unseen AOI 39/78.
5. **финал**: две точки входа — web и private_features → submission.

Перед выступлением:

```text
- docker compose уже up
- готовый report/submission на месте
- минимум один live analysis уже сохранён
- браузер открыт на localhost:8080
- терминал с `docker compose ps`
```

Если сеть умерла — competition ветка полностью локальная. Live новый job не запускаем, показываем сохранённый result.
