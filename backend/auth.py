"""Autenticación: valida el JWT de Supabase que envía el programa.

El token se verifica preguntándole a Supabase Auth (/auth/v1/user). Así sirve
con cualquier tipo de firma de JWT del proyecto y no hace falta guardar el
secreto JWT. El resultado se guarda 5 minutos en memoria para no repetir la
consulta en cada petición. El user_id sale siempre del token, nunca del cuerpo.
"""
import hashlib
import threading
import time
from dataclasses import dataclass

from fastapi import Header

from db import get_db
from errores import ErrorApi

_CACHE: dict[str, tuple[float, "Usuario"]] = {}
_LOCK = threading.Lock()
_TTL = 300


@dataclass(frozen=True)
class Usuario:
    id: str
    email: str
    token: str


def _clave(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def usuario_actual(authorization: str | None = Header(default=None)) -> Usuario:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ErrorApi(401, "no_autenticado", "Inicia sesión para continuar.")
    token = authorization.split(" ", 1)[1].strip()
    clave = _clave(token)
    ahora = time.time()
    with _LOCK:
        guardado = _CACHE.get(clave)
        if guardado and guardado[0] > ahora:
            return guardado[1]
    datos = get_db().usuario_de_token(token)
    if not datos or not datos.get("id"):
        raise ErrorApi(401, "sesion_vencida", "Tu sesión venció. Vuelve a iniciar sesión.")
    usuario = Usuario(id=datos["id"], email=datos.get("email") or "", token=token)
    with _LOCK:
        if len(_CACHE) > 5000:
            _CACHE.clear()
        _CACHE[clave] = (ahora + _TTL, usuario)
    return usuario
