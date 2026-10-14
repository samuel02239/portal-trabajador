"""Límite de solicitudes por usuario (ventana deslizante).

Se lleva en Supabase (función registrar_solicitud) para que valga igual en todos los procesos del servidor y no
se reinicie cuando el servidor se reinicia. Si la base de datos no responde, se usa un registro en memoria.
"""
import logging
import threading
import time
from collections import defaultdict, deque

from db import get_db
from errores import ErrorApi

log = logging.getLogger("portal.limites")
_REGISTRO: dict[tuple[str, str], deque] = defaultdict(deque)
_LOCK = threading.Lock()


def _error(espera_s: float) -> ErrorApi:
    minutos = max(1, int(espera_s / 60) + 1)
    return ErrorApi(429, "limite_solicitudes",
                    f"Hiciste muchas solicitudes seguidas. Intenta de nuevo en {minutos} minutos.")


def _en_memoria(user_id: str, accion: str, maximo: int, ventana_s: int) -> None:
    ahora = time.time()
    with _LOCK:
        cola = _REGISTRO[(user_id, accion)]
        while cola and cola[0] <= ahora - ventana_s:
            cola.popleft()
        if len(cola) >= maximo:
            raise _error(cola[0] + ventana_s - ahora)
        cola.append(ahora)


def verificar(user_id: str, accion: str, maximo: int, ventana_s: int = 3600) -> None:
    try:
        r = get_db().rpc("registrar_solicitud", {"p_user": user_id, "p_accion": accion,
                                                 "p_maximo": maximo, "p_ventana_s": ventana_s})
    except Exception as exc:  # noqa: BLE001 - sin base de datos no se bloquea al usuario: se cuenta en memoria
        log.warning("Límite de solicitudes en memoria (%s)", type(exc).__name__)
        _en_memoria(user_id, accion, maximo, ventana_s)
        return
    if isinstance(r, dict) and r.get("ok") is False:
        raise _error(float(r.get("espera_s") or 60))
