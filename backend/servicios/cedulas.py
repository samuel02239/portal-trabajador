"""Cédula del contratista: normalización, verificación en la minuta y vínculo con la cuenta."""
from __future__ import annotations

import re

from db import get_db
from errores import ErrorApi


def normalizar(cedula: str | None) -> str:
    return re.sub(r"\D", "", cedula or "")


def aparece_en_texto(cedula: str, texto: str) -> bool:
    """¿La cédula está escrita en el documento? Admite puntos, comas o espacios entre dígitos (1.012.345.678)
    y exige que no sea parte de un número más largo (un teléfono…) ni un NIT (890480184-4)."""
    digitos = normalizar(cedula)
    if len(digitos) < 5:
        return False
    patron = r"(?<!\d)(?<!\d[.,])" + r"[.,\s]?".join(digitos) + r"(?!\d|[.,]\d|\s?-\s?\d)"
    return re.search(patron, texto or "") is not None


def ocultar_correo(correo: str | None) -> str:
    """persona.prueba@gmail.com -> pe***@gmail.com"""
    if not correo or "@" not in correo:
        return "otra cuenta"
    usuario, dominio = correo.split("@", 1)
    return f"{usuario[:2]}***@{dominio}"


def ocultar_cedula(cedula: str) -> str:
    return f"****{cedula[-4:]}" if len(cedula) > 4 else cedula


def vincular(user_id: str, cedula: str) -> str:
    """Fija la cédula en la cuenta (una cédula = una cuenta). Lanza ErrorApi con un mensaje claro si no se puede."""
    r = get_db().rpc("vincular_cedula", {"p_user": user_id, "p_cedula": cedula})
    if r.get("ok"):
        return r["cedula"]
    motivo = r.get("motivo")
    if motivo == "cedula_en_uso":
        raise ErrorApi(409, "cedula_en_uso",
                       f"La cédula de este contrato ya está vinculada a otra cuenta ({ocultar_correo(r.get('correo'))}). "
                       "Cada persona puede tener una sola cuenta: inicia sesión con esa cuenta. Si no la reconoces, "
                       "escríbenos para revisarlo.")
    if motivo == "cedula_distinta":
        raise ErrorApi(409, "cedula_distinta",
                       f"Tu cuenta está vinculada a la cédula {ocultar_cedula(r.get('cedula_cuenta', ''))}. "
                       "Solo puedes registrar contratos a tu nombre; para otra persona se necesita otra cuenta.")
    raise ErrorApi(400, "cedula_invalida", "Escribe un número de cédula válido (solo números).")
