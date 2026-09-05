.PHONY: build up down logs test inspect benchmark competition infer validate

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

test:
	docker compose run --rm api python -m pytest -q /app/analytics/tests /app/backend/tests

inspect:
	docker compose run --rm api florascope-core inspect --dataset /data/input/train_dataset.csv

benchmark:
	docker compose run --rm api florascope-core benchmark --train /data/input/train_dataset.csv --fast

competition:
	docker compose run --rm api florascope-core competition --train /data/input/train_dataset.csv --input /data/input/test_dataset.csv --artifacts /artifacts/competition_model --output /data/output --fast

infer:
	docker compose run --rm api florascope-core infer --model /artifacts/competition_model --input /data/input/private_features.csv --output /data/output

validate:
	docker compose run --rm api florascope-core validate-submission --test /data/input/test_dataset.csv --submission /data/output/submission.csv
