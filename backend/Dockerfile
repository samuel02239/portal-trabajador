# Backend del Portal del Trabajador para la nube (Render u otro servicio con Docker). Ver DESPLIEGUE.md.
#
# - LibreOffice convierte el informe (y las evidencias Word/Excel, para sacarles capturas) a PDF.
# - Fuentes con las mismas medidas que las de la plantilla: Liberation Sans = Arial, Liberation Sans Narrow =
#   Arial Narrow (solo viene en Debian 12 "bookworm", por eso la imagen queda fija), Carlito = Calibri,
#   Liberation Mono = Courier New.
# - Corre con un usuario sin permisos de administrador.
# - Las llaves NO van en la imagen: se configuran como variables de entorno del servicio.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libreoffice-writer-nogui libreoffice-calc-nogui fonts-liberation fonts-crosextra-carlito fonts-dejavu-core fontconfig \
 && rm -rf /var/lib/apt/lists/* \
 && fc-cache -f \
 && (soffice --version || echo "AVISO: soffice no respondió; /api/health dirá si hay PDF") \
 && (fc-list | grep -qi "Liberation Sans Narrow" || echo "AVISO: no se encontró Liberation Sans Narrow")

RUN useradd --create-home --uid 10001 portal
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=portal:portal . .
USER portal
ENV HOME=/home/portal \
    PORT=8000 \
    WEB_CONCURRENCY=1

# Falla la construcción si falta alguna dependencia de Python (mejor aquí que con usuarios conectados)
RUN python -c "import main"

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8000'), timeout=4)"

# --proxy-headers: la IP real del usuario llega en X-Forwarded-For desde el proxy del servicio en la nube
# (la usa el límite de solicitudes por IP). WEB_CONCURRENCY = procesos; súbelo si el plan tiene más memoria.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*' --no-server-header --timeout-keep-alive 75"]
