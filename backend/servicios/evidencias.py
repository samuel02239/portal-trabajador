"""Evidencias (anexos): tipo de archivo y descripción del anexo acorde a la actividad y la obligación."""
from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field, field_validator

import prompts
from ia import IAError, llamar_ia
from schemas import a_texto

log = logging.getLogger("portal.evidencias")

TIPOS = {"png": "imagen", "jpg": "imagen", "jpeg": "imagen", "pdf": "documento", "docx": "documento",
         "xlsx": "hoja de cálculo"}
PREFIJOS = {"imagen": "Registro fotográfico de", "documento": "Documento soporte de",
            "hoja de cálculo": "Archivo de soporte de"}


def tipo_de(nombre: str) -> str:
    ext = (nombre or "").lower().rsplit(".", 1)[-1]
    return TIPOS.get(ext, "documento")


def es_imagen(nombre: str) -> bool:
    return tipo_de(nombre) == "imagen"


class _DescripcionIA(BaseModel):
    descripcion: str = Field(min_length=8, max_length=300)

    @field_validator("descripcion", mode="before")
    @classmethod
    def _limpia(cls, v):
        s = a_texto(v) or ""
        return s.rstrip(".").strip()


def descripcion_respaldo(actividad: str, tipo: str) -> str:
    """Sin IA: 'Registro fotográfico de: <actividad resumida>'."""
    texto = re.split(r",\s*(en desarrollo|en el marco|en cumplimiento)", actividad or "", maxsplit=1)[0]
    texto = texto.strip().rstrip(".")
    if texto:
        texto = texto[0].lower() + texto[1:]
    return f"{PREFIJOS[tipo]} la actividad: {texto}"[:240] if texto else f"{PREFIJOS[tipo]} la actividad"


def describir(actividad: str, obligacion: str, nombre_archivo: str, user_id: str | None = None) -> str:
    """Descripción del anexo acorde a la actividad y la obligación (IA con respaldo por reglas)."""
    tipo = tipo_de(nombre_archivo)
    try:
        r, _ = llamar_ia("describir_evidencia", [
            {"role": "system", "content": prompts.SISTEMA_EVIDENCIA},
            {"role": "user", "content": prompts.usuario_evidencia(actividad, obligacion, tipo)},
        ], _DescripcionIA, user_id=user_id, max_tokens=300, temperatura=0.2)
        return r.descripcion
    except IAError as exc:
        log.info("Descripción de evidencia sin IA: %s", str(exc)[:120])
        return descripcion_respaldo(actividad, tipo)
