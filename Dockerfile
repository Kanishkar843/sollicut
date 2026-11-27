# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN --mount=type=secret,id=corporate_ca if [ -f /run/secrets/corporate_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/corporate_ca; fi; npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm AS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libraqm0 fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock backend/requirements.lock
RUN --mount=type=secret,id=corporate_ca if [ -f /run/secrets/corporate_ca ]; then export PIP_CERT=/run/secrets/corporate_ca; fi; pip install --no-cache-dir -r backend/requirements.lock

FROM dependencies AS model
ARG SOLLICUT_PROFILE=balanced
ARG SOLLICUT_ASR_MODEL=small
ARG SOLLICUT_INDIC_ASR_ENABLED=true
ENV SOLLICUT_PROFILE=${SOLLICUT_PROFILE} SOLLICUT_ASR_MODEL=${SOLLICUT_ASR_MODEL} SOLLICUT_MODEL_DIR=/models SOLLICUT_INDIC_ASR_ENABLED=${SOLLICUT_INDIC_ASR_ENABLED} SOLLICUT_INDIC_MODEL_DIR=/models/indicconformer-ta
COPY scripts/download_model.py scripts/download_model.py
RUN --mount=type=secret,id=corporate_ca if [ -f /run/secrets/corporate_ca ]; then export SSL_CERT_FILE=/run/secrets/corporate_ca; fi; timeout 900 python scripts/download_model.py || echo 'ASR model acquisition failed; HTTP UI will still start. Rebuild to enable speech.'

FROM dependencies AS runtime
ARG SOLLICUT_PROFILE=balanced
ARG SOLLICUT_ASR_MODEL=small
ARG SOLLICUT_INDIC_ASR_ENABLED=true
ENV SOLLICUT_PROFILE=${SOLLICUT_PROFILE} SOLLICUT_ASR_MODEL=${SOLLICUT_ASR_MODEL} SOLLICUT_MODEL_DIR=/models SOLLICUT_INDIC_ASR_ENABLED=${SOLLICUT_INDIC_ASR_ENABLED} SOLLICUT_INDIC_MODEL_DIR=/models/indicconformer-ta SOLLICUT_ASR_ENGINE=faster-whisper SOLLICUT_ASR_DEVICE=cpu SOLLICUT_ASR_COMPUTE_TYPE=int8 SOLLICUT_ASR_THREADS=4 SOLLICUT_DATA_DIR=/data SOLLICUT_PORT=8080 PYTHONUNBUFFERED=1
COPY --from=model /models /models
COPY backend backend
COPY assets assets
COPY scripts scripts
COPY tests tests
COPY --from=web /web/dist frontend/dist
RUN python scripts/generate_demo_assets.py && python -c "from PIL import features; assert features.check_feature('raqm')" && useradd --create-home --uid 10001 app && mkdir -p /data && chown -R app:app /data /app
USER app
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
