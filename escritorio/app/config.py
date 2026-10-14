"""Configuración del programa: API_BASE_URL, SUPABASE_URL y SUPABASE_ANON_KEY.

Se leen de un .env junto al .exe (si existe) y luego del .env empaquetado.
Solo contiene valores públicos: la llave anon/publishable no da acceso a datos
ajenos porque todas las tablas tienen RLS.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from platformdirs import user_cache_dir, user_log_dir

APP_NOMBRE = "Portal del Trabajador"
APP_ORG = "PortalTrabajador"
VERSION = "1.1.0"

EMPAQUETADO = getattr(sys, "frozen", False)
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
RECURSOS = BASE / "recursos"

if EMPAQUETADO:
    load_dotenv(Path(sys.executable).with_name(".env"))  # permite cambiar el servidor sin reinstalar
load_dotenv(BASE / ".env")

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# "integrado": el programa enciende el backend dentro de sí mismo al abrirse y lo apaga al cerrarse.
# "remoto": el programa usa el backend que está en API_BASE_URL (servidor propio o en la nube).
MODO_BACKEND = os.environ.get("MODO_BACKEND", "remoto").strip().lower()
PUERTO_BACKEND = int(os.environ.get("PUERTO_BACKEND", "8000"))


def version_tupla(version: str) -> tuple[int, ...]:
    partes = []
    for p in str(version).split("."):
        digitos = "".join(c for c in p if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    return tuple(partes)


def es_local(url: str) -> bool:
    return any(h in url for h in ("://127.0.0.1", "://localhost"))


def problema_de_configuracion() -> str | None:
    """Un servidor en internet siempre debe ir por https (cifrado); si no, se rechaza."""
    if MODO_BACKEND == "remoto" and not es_local(API_BASE_URL) and not API_BASE_URL.startswith("https://"):
        return "La dirección del servidor (API_BASE_URL) debe empezar por https:// para que la conexión vaya cifrada."
    if not SUPABASE_URL.startswith("https://"):
        return "SUPABASE_URL debe empezar por https://."
    return None


def carpeta_backend() -> Path | None:
    """Dónde está el código del backend para el modo integrado."""
    candidatos = [os.environ.get("PORTAL_BACKEND_DIR"), BASE / "backend", BASE.parent / "backend"]
    for c in candidatos:
        if c and (Path(c) / "main.py").exists():
            return Path(c)
    return None


def archivo_env_backend() -> Path | None:
    """Llaves del backend integrado. Instalado: junto al .exe o en %LOCALAPPDATA%; nunca dentro del instalador."""
    if not EMPAQUETADO:
        return None  # en desarrollo se usa backend/.env
    for c in (Path(sys.executable).with_name("backend.env"),
              Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_ORG / "backend.env"):
        if c.exists():
            return c
    return None

CARPETA_CACHE = Path(user_cache_dir(APP_ORG, appauthor=False))
CARPETA_LOGS = Path(user_log_dir(APP_ORG, appauthor=False))
MAX_ARCHIVO = 20 * 1024 * 1024
MAX_ACTIVIDAD = 2000
