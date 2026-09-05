# api v1

OpenAPI после запуска: `http://localhost:8000/docs`.

Основное:

```text
GET    /api/v1/health
GET    /api/v1/system

GET    /api/v1/fields
POST   /api/v1/fields
PUT    /api/v1/fields/{id}
DELETE /api/v1/fields/{id}
POST   /api/v1/fields/discover

POST   /api/v1/analyses
GET    /api/v1/analyses
GET    /api/v1/analyses/{id}
GET    /api/v1/analyses/{id}/tiles/{layer}/{z}/{x}/{y}.png

GET    /api/v1/jobs/{id}

POST   /api/v1/benchmark/files/{train|test}
POST   /api/v1/benchmark/run
GET    /api/v1/benchmark/report
GET    /api/v1/benchmark/submission
GET    /api/v1/benchmark/validate
GET    /api/v1/benchmark/polygons
GET    /api/v1/benchmark/series/{polygon_id}
GET    /api/v1/benchmark/events
```

`POST /analyses` возвращает job, дальше фронт поллит `/jobs/{id}`. Так же работает benchmark.
