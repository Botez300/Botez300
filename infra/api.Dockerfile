# Build context: repository root.
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY services/indicators services/indicators
COPY services/data-ingestion services/data-ingestion
COPY services/market-scanner services/market-scanner
COPY apps/api apps/api
RUN pip install ./services/indicators ./services/data-ingestion ./services/market-scanner ./apps/api
RUN useradd --system --uid 10001 legion
USER legion
WORKDIR /app/apps/api
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"
# Migrations run on start so a fresh database is usable immediately.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn legion_api.main:app --host 0.0.0.0 --port 8000"]
