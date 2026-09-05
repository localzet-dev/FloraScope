# windows / docker desktop

PowerShell из корня проекта:

```powershell
Copy-Item .env.example .env
docker compose build --no-cache
docker compose up -d
```

Проверка:

```powershell
docker compose ps
docker compose logs --tail=100 api
docker compose logs --tail=100 web
```

Открыть:

```text
http://localhost:8080
http://localhost:8000/docs
```

Полный локальный check готовой модели:

```powershell
.\scripts\check_release.ps1
```

Если нужно заново обучить модель + получить submission:

```powershell
docker compose run --rm api florascope-core competition `
  --train /data/input/train_dataset.csv `
  --input /data/input/test_dataset.csv `
  --artifacts /artifacts/competition_model `
  --output /data/output `
  --fast
```

Если backend упал:

```powershell
docker compose logs --no-color --tail=250 api
```

Если web не собрался:

```powershell
docker compose build --no-cache web
```

Node локально ставить не нужно — frontend собирается в своём Docker stage.
