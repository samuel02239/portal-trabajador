"""Cuentas de prueba sin límite (tabla public.cuentas_sin_limite). La decisión la toma la base de datos."""
import threading
import time

from db import get_db

_CACHE: dict[str, tuple[float, bool]] = {}
_LOCK = threading.Lock()
_TTL = 60


def sin_limite(user_id: str) -> bool:
    ahora = time.time()
    with _LOCK:
        guardado = _CACHE.get(user_id)
        if guardado and guardado[0] > ahora:
            return guardado[1]
    valor = bool(get_db().rpc("es_sin_limite", {"p_user": user_id}))
    with _LOCK:
        _CACHE[user_id] = (ahora + _TTL, valor)
    return valor
