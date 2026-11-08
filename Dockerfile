# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS wheels

ENV PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10
WORKDIR /build

COPY requirements.txt requirements-dev.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir /wheels -r requirements.txt -r requirements-dev.txt

FROM python:3.12-slim-bookworm AS runtime

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home --home-dir /home/app app \
    && mkdir -p /home/app/.cache/chroma \
    && chown -R 10001:10001 /home/app

WORKDIR /app

COPY --from=wheels /wheels /wheels
COPY requirements.txt ./
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY --chown=10001:10001 app ./app

USER 10001
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM runtime AS dev

USER 0
COPY --from=wheels /wheels /wheels
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements-dev.txt \
    && rm -rf /wheels
COPY --chown=10001:10001 tests ./tests
COPY --chown=10001:10001 pytest.ini ./
USER 10001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
