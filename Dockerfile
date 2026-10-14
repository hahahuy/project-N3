# Build the browser bundle separately so the runtime image only contains the
# Python API, its dependencies, and the files required to serve the website.
FROM node:22-bookworm-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    R2S_PROJECT_ROOT=/app \
    R2S_ARTIFACT_ROOT=scenarios \
    R2S_OUTPUT_ROOT=reports

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir ".[web]"

COPY scenarios/ ./scenarios/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN mkdir -p /app/reports \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

CMD ["uvicorn", "r2s_web.app:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
