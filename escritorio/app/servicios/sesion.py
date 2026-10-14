"""Sesión: el token de refresco se guarda en el Administrador de credenciales de Windows (keyring).

Nunca se escribe en un archivo de texto. El token de acceso solo vive en memoria.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass

import keyring
from keyring.errors import KeyringError

log = logging.getLogger("portal.sesion")

# Las pruebas automáticas usan otro nombre para no tocar la sesión real guardada en el equipo
SERVICIO = os.environ.get("PORTAL_KEYRING_SERVICIO", "PortalTrabajador")
CUENTA = "refresh_token"


@dataclass
class Sesion:
    access_token: str
    refresh_token: str
    expira: float          # epoch en segundos
    user_id: str
    email: str

    @classmethod
    def desde_gotrue(cls, d: dict) -> "Sesion":
        usuario = d.get("user") or {}
        expira = d.get("expires_at") or (time.time() + int(d.get("expires_in") or 3600))
        return cls(d["access_token"], d["refresh_token"], float(expira), usuario.get("id", ""),
                   usuario.get("email", ""))

    def por_vencer(self, margen: int = 60) -> bool:
        return time.time() > self.expira - margen


def guardar_refresh(token: str) -> None:
    try:
        keyring.set_password(SERVICIO, CUENTA, token)
    except KeyringError as exc:
        log.warning("No se pudo guardar la sesión en el equipo: %s", type(exc).__name__)


def leer_refresh() -> str | None:
    try:
        return keyring.get_password(SERVICIO, CUENTA)
    except KeyringError:
        return None


def borrar_refresh() -> None:
    try:
        keyring.delete_password(SERVICIO, CUENTA)
    except KeyringError:
        pass


class GestorSesion:
    """Guarda la sesión actual y la renueva cuando vence (seguro entre hilos)."""

    def __init__(self, auth):
        self.auth = auth
        self.sesion: Sesion | None = None
        self._lock = threading.Lock()

    def establecer(self, sesion: Sesion | None) -> None:
        self.sesion = sesion
        if sesion:
            guardar_refresh(sesion.refresh_token)
        else:
            borrar_refresh()

    def restaurar(self) -> Sesion | None:
        """Intenta entrar con el token guardado en el equipo."""
        token = leer_refresh()
        if not token:
            return None
        nueva = self.auth.refrescar(token)
        self.establecer(nueva)
        return nueva

    def token(self, forzar: bool = False) -> str | None:
        with self._lock:
            if not self.sesion:
                return None
            if forzar or self.sesion.por_vencer():
                self.establecer(self.auth.refrescar(self.sesion.refresh_token))
            return self.sesion.access_token
