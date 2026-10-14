"""Copia local de las evidencias: Documentos/Portal del Trabajador/Evidencias/AAAA-MM/.

Al elegir una imagen o un documento, primero se guarda una copia en esta carpeta
(así queda en el equipo aunque el original se mueva o se borre) y desde ahí se sube.
"""
from __future__ import annotations

import os
import re
import shutil
import unicodedata
from datetime import date
from pathlib import Path

from PySide6.QtCore import QStandardPaths

EXTENSIONES_IMAGEN = {".png", ".jpg", ".jpeg"}


def carpeta_base() -> Path:
    otra = os.environ.get("PORTAL_CARPETA_EVIDENCIAS")  # para pruebas
    if otra:
        return Path(otra)
    documentos = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or str(Path.home())
    return Path(documentos) / "Portal del Trabajador" / "Evidencias"


def carpeta_del_mes(fecha: date) -> Path:
    carpeta = carpeta_base() / f"{fecha.year:04d}-{fecha.month:02d}"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _nombre_limpio(nombre: str) -> str:
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    base = re.sub(r"[^\w.\-]+", "_", base).strip("._") or "evidencia"
    return base[:90]


def guardar_copia(origen: str | Path, fecha: date) -> Path:
    """Copia el archivo a la carpeta del mes con el nombre 'AAAA-MM-DD_nombre' (sin pisar otros)."""
    origen = Path(origen)
    carpeta = carpeta_del_mes(fecha)
    if origen.parent.resolve() == carpeta.resolve():
        return origen  # ya está en la carpeta de evidencias
    destino = carpeta / f"{fecha.isoformat()}_{_nombre_limpio(origen.name)}"
    n = 2
    while destino.exists():
        destino = carpeta / f"{fecha.isoformat()}_{n}_{_nombre_limpio(origen.name)}"
        n += 1
    shutil.copy2(origen, destino)
    return destino


def es_imagen(ruta: str | Path) -> bool:
    return Path(ruta).suffix.lower() in EXTENSIONES_IMAGEN
