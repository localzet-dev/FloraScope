FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4 \
    FLORASCOPE_DATA_DIR=/data \
    FLORASCOPE_ARTIFACTS_DIR=/artifacts

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libexpat1 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY analytics ./analytics
COPY backend ./backend
RUN python -m pip install --no-cache-dir --upgrade "pip==26.2.1" \
    && python -m pip install --no-cache-dir "./analytics[dev]" "./backend[dev]"

EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

CMD ["uvicorn", "florascope_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
