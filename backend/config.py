"""Configuración del backend: lee backend/.env y providers.json."""
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
# Cuando el programa de escritorio enciende el backend integrado, puede indicar otro archivo de llaves
if os.environ.get("PORTAL_BACKEND_ENV"):
    load_dotenv(os.environ["PORTAL_BACKEND_ENV"])
load_dotenv(BASE / ".env")

MAX_ARCHIVO = 20 * 1024 * 1024  # 20 MB
CLASIFICACIONES_POR_HORA = 30
EVIDENCIAS_POR_HORA = 60      # cada evidencia pide a la IA la descripción del anexo
GENERACIONES_POR_HORA = 30    # regenerar no cobra cupo, pero ocupa la conversión a PDF de todos


def _env(nombre: str, defecto: str = "") -> str:
    return os.environ.get(nombre, defecto).strip()


def _lista(*nombres: str) -> tuple[str, ...]:
    """Une variables con una o varias llaves (separadas por coma, punto y coma o salto de línea), sin repetir."""
    salida: list[str] = []
    for nombre in nombres:
        for parte in re.split(r"[,;\s]+", _env(nombre)):
            if parte and parte not in salida:
                salida.append(parte)
    return tuple(salida)


@dataclass(frozen=True)
class Config:
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    openrouter_api_keys: tuple[str, ...]
    openrouter_models: str
    wompi_public_key: str
    wompi_private_key: str
    wompi_events_secret: str
    wompi_integrity_secret: str
    wompi_env: str
    wompi_redirect_url: str
    libreoffice_path: str
    version_minima_escritorio: str
    url_descarga_escritorio: str

    @property
    def openrouter_api_key(self) -> str:
        return self.openrouter_api_keys[0] if self.openrouter_api_keys else ""

    @property
    def wompi_configurado(self) -> bool:
        return bool(self.wompi_public_key and self.wompi_integrity_secret)


_ENTORNOS_WOMPI = {"sandbox": "sandbox", "pruebas": "sandbox", "test": "sandbox",
                   "production": "production", "produccion": "production", "producción": "production",
                   "prod": "production"}
# Prefijos de las llaves de Wompi según el entorno (pruebas, producción)
_PREFIJOS_WOMPI = {
    "WOMPI_PUBLIC_KEY": ("wompi_public_key", "pub_test_", "pub_prod_"),
    "WOMPI_PRIVATE_KEY": ("wompi_private_key", "prv_test_", "prv_prod_"),
    "WOMPI_EVENTS_SECRET": ("wompi_events_secret", "test_events_", "prod_events_"),
    "WOMPI_INTEGRITY_SECRET": ("wompi_integrity_secret", "test_integrity_", "prod_integrity_"),
}


def revisar(c: "Config | None" = None) -> list[str]:
    """Errores de configuración frecuentes al desplegar. Solo nombra variables; nunca muestra su valor."""
    c = c or cfg
    avisos = []
    if not (c.supabase_url and c.supabase_anon_key and c.supabase_service_key):
        avisos.append("Faltan SUPABASE_URL, SUPABASE_ANON_KEY o SUPABASE_SERVICE_ROLE_KEY.")
    if c.supabase_service_key.startswith("sb_publishable_"):
        avisos.append("SUPABASE_SERVICE_ROLE_KEY tiene la llave pública: debe ser la secreta (sb_secret_...).")
    if not c.openrouter_api_keys:
        avisos.append("Falta OPENROUTER_API_KEYS: la IA no funcionará.")
    if c.wompi_env not in ("sandbox", "production"):
        avisos.append("WOMPI_ENV debe ser sandbox o production.")
    elif any(getattr(c, campo) for campo, _, _ in _PREFIJOS_WOMPI.values()):
        for nombre, (campo, prueba, produccion) in _PREFIJOS_WOMPI.items():
            valor = getattr(c, campo)
            esperado = prueba if c.wompi_env == "sandbox" else produccion
            if not valor:
                avisos.append(f"Falta {nombre}.")
            elif not valor.startswith(esperado):
                avisos.append(f"{nombre} no corresponde a WOMPI_ENV={c.wompi_env} (debe empezar por {esperado}).")
    return avisos


def cargar() -> Config:
    return Config(
        supabase_url=_env("SUPABASE_URL").rstrip("/"),
        supabase_anon_key=_env("SUPABASE_ANON_KEY"),
        supabase_service_key=_env("SUPABASE_SERVICE_ROLE_KEY"),
        # Varias llaves: si una falla (sin saldo, inválida o con límite), se pasa a la siguiente
        openrouter_api_keys=_lista("OPENROUTER_API_KEYS", "OPENROUTER_API_KEY"),
        openrouter_models=_env("OPENROUTER_MODELS"),
        wompi_public_key=_env("WOMPI_PUBLIC_KEY"),
        wompi_private_key=_env("WOMPI_PRIVATE_KEY"),
        wompi_events_secret=_env("WOMPI_EVENTS_SECRET"),
        wompi_integrity_secret=_env("WOMPI_INTEGRITY_SECRET"),
        # Acepta "produccion" o "pruebas"; un valor desconocido se deja tal cual para que revisar() lo avise
        wompi_env=_ENTORNOS_WOMPI.get(_env("WOMPI_ENV").lower() or "sandbox", _env("WOMPI_ENV").lower()),
        wompi_redirect_url=_env("WOMPI_REDIRECT_URL"),
        libreoffice_path=_env("LIBREOFFICE_PATH"),
        version_minima_escritorio=_env("VERSION_MINIMA_ESCRITORIO", "1.1.0") or "1.1.0",
        url_descarga_escritorio=_env("URL_DESCARGA_ESCRITORIO"),
    )


cfg = cargar()


def proveedores_ia() -> list[dict]:
    """Modelos activos en orden de respaldo.

    Fuente principal: providers.json. Si no existe, se usa OPENROUTER_MODELS
    (lista separada por comas), como describe la especificación.
    """
    ruta = BASE / "providers.json"
    if ruta.exists():
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        return [p for p in datos.get("providers", [])
                if p.get("model") and p.get("enabled", True) is not False]
    return [{"name": m.strip(), "model": m.strip()}
            for m in cfg.openrouter_models.split(",") if m.strip()]
