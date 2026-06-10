# NOVA — imagen del servicio (FastAPI + WebSocket). Multi-stage, no-root.
# OJO: la imagen real del ASUS se buildea EN el ASUS (x86_64 + GPU). En el Mac
# (arm64) el build es solo validación del Dockerfile.

# ---------- build ----------
FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /src

# venv aislado que después copiamos al runtime liviano.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copiar solo lo necesario para instalar el paquete (con el server extra).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[server]"

# ---------- runtime ----------
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    NOVA_HOST=0.0.0.0 \
    NOVA_PORT=8000 \
    NOVA_LOG_DIR=/app/logs

# Usuario no-root.
RUN groupadd -r nova && useradd -r -g nova -u 10001 -d /app nova

COPY --from=build /opt/venv /opt/venv

WORKDIR /app
# Carpeta de logs escribible (el resto del fs puede ir read-only en compose).
RUN mkdir -p /app/logs && chown -R nova:nova /app

USER nova
EXPOSE 8000

# Healthcheck sin curl (no está en slim): urllib contra /health.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4).status==200 else 1)"

CMD ["python", "-m", "nova.app"]
