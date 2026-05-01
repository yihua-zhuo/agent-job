FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy source before installing (so egg_info can find src/)
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Now install — src/ exists so editable install succeeds
RUN pip install --no-cache-dir -e ".[dev]"

ENV HOST=0.0.0.0
ENV PYTHONPATH=/app/src

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

CMD ["uvicorn", "--host", "0.0.0.0", "--port", "8080", "--workers", "2", "main:app"]
