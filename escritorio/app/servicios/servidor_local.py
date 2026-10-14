"""Backend integrado: el programa enciende el backend dentro de sí mismo y lo apaga al cerrarse.

No abre ninguna ventana: el servidor FastAPI corre en un hilo del mismo programa,
escuchando solo en 127.0.0.1 (nadie más en la red puede conectarse). Si ya hay un
backend respondiendo en el puerto configurado (por ejemplo, abierto con
iniciar_backend.bat), se usa ese y no se enciende otro.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path

import httpx

from app import config
from app.servicios.errores import ErrorApp

log = logging.getLogger("portal.servidor")


def _responde(url: str, timeout: float = 1.5) -> bool:
    try:
        return httpx.get(f"{url}/api/health", timeout=timeout).status_code == 200
    except httpx.HTTPError:
        return False


def _puerto_libre(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", puerto))
            return True
        except OSError:
            return False


def _puerto_cualquiera() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServidorLocal:
    def __init__(self):
        self.puerto: int | None = None
        self.servidor = None
        self.hilo: threading.Thread | None = None
        self.propio = False
        self._lock = threading.Lock()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.puerto}"

    def asegurar(self, puerto: int | None = None, reutilizar: bool = True, espera: float = 45) -> str:
        """Devuelve la URL de un backend que responde; si no hay ninguno, enciende el integrado."""
        with self._lock:
            if self.propio and self.hilo and self.hilo.is_alive():
                return self.url
            puerto = puerto or config.PUERTO_BACKEND
            if reutilizar and _responde(f"http://127.0.0.1:{puerto}"):
                self.puerto = puerto
                log.info("Se usa el backend que ya estaba encendido en el puerto %s", puerto)
                return self.url
            carpeta = config.carpeta_backend()
            if not carpeta:
                raise ErrorApp("No se encontró el backend para encenderlo. Revisa la instalación del programa.",
                               "sin_backend")
            self.puerto = puerto if _puerto_libre(puerto) else _puerto_cualquiera()
            aplicacion = self._cargar_aplicacion(carpeta)

            import uvicorn
            ajustes = uvicorn.Config(aplicacion, host="127.0.0.1", port=self.puerto, log_config=None,
                                     access_log=False, lifespan="off")
            self.servidor = uvicorn.Server(ajustes)
            self.hilo = threading.Thread(target=self.servidor.run, name="backend-integrado", daemon=True)
            self.hilo.start()
            self.propio = True
            fin = time.monotonic() + espera
            while time.monotonic() < fin:
                if _responde(self.url, 1.0):
                    log.info("Backend integrado encendido en %s", self.url)
                    return self.url
                if not self.hilo.is_alive():
                    break
                time.sleep(0.25)
            self.propio = False
            raise ErrorApp("No se pudo encender el servidor interno del programa. Revisa el registro en "
                           f"{config.CARPETA_LOGS}.", "sin_backend")

    @staticmethod
    def _cargar_aplicacion(carpeta: Path):
        """Importa backend/main.py con otro nombre para no chocar con el main.py del programa."""
        env = config.archivo_env_backend()
        if env:
            os.environ["PORTAL_BACKEND_ENV"] = str(env)
        if str(carpeta) not in sys.path:
            sys.path.insert(0, str(carpeta))
        spec = importlib.util.spec_from_file_location("portal_backend_main", carpeta / "main.py")
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo.app

    def detener(self) -> None:
        if self.servidor is not None and self.propio:
            self.servidor.should_exit = True
            if self.hilo:
                self.hilo.join(timeout=6)
            self.propio = False
            log.info("Backend integrado apagado")


_servidor: ServidorLocal | None = None


def servidor() -> ServidorLocal:
    global _servidor
    if _servidor is None:
        _servidor = ServidorLocal()
    return _servidor
