"""Protecciones generales de la API publicada en internet.

- Límite de tamaño del cuerpo (archivos de hasta 20 MB + margen).
- Límite de solicitudes por dirección IP (frena abusos y ataques de fuerza bruta).
- Encabezados de seguridad y respuestas sin caché (llevan datos personales).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

MAX_CUERPO = 25 * 1024 * 1024
SOLICITUDES_POR_MINUTO_IP = 300   # generoso: en una oficina muchos usuarios salen por la misma IP
WEBHOOK_POR_MINUTO_IP = 60

_registro: dict[tuple[str, str], deque] = defaultdict(deque)
_lock = threading.Lock()


def _ip(request: Request) -> str:
    # Con uvicorn --proxy-headers, request.client ya es la IP real del usuario detrás del proxy del servidor
    return request.client.host if request.client else "desconocida"


def _excede(clave: tuple[str, str], maximo: int, ventana: float = 60.0) -> bool:
    ahora = time.monotonic()
    with _lock:
        cola = _registro[clave]
        while cola and cola[0] <= ahora - ventana:
            cola.popleft()
        if len(cola) >= maximo:
            return True
        cola.append(ahora)
        if len(_registro) > 50_000:  # evita crecer sin límite
            _registro.clear()
        return False


def _error(status: int, codigo: str, mensaje: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"codigo": codigo, "mensaje": mensaje}})


def registrar(app: FastAPI) -> None:
    @app.middleware("http")
    async def proteger(request: Request, siguiente):
        largo = request.headers.get("content-length")
        if largo and largo.isdigit() and int(largo) > MAX_CUERPO:
            return _error(413, "solicitud_muy_grande", "El archivo o la solicitud es demasiado grande.")
        ruta = request.url.path
        if ruta != "/api/health":
            grupo, maximo = (("webhook", WEBHOOK_POR_MINUTO_IP) if ruta == "/api/pagos/webhook"
                             else ("general", SOLICITUDES_POR_MINUTO_IP))
            if _excede((_ip(request), grupo), maximo):
                return _error(429, "demasiadas_solicitudes", "Demasiadas solicitudes seguidas. Espera un momento.")
        respuesta = await siguiente(request)
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        respuesta.headers["Cache-Control"] = "no-store"
        return respuesta
