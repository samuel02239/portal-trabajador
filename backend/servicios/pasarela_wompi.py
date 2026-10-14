"""Pasarela Wompi (Colombia): Web Checkout + eventos firmados.

Documentación usada (docs.wompi.co):
- Web Checkout: GET https://checkout.wompi.co/p/ con public-key, currency,
  amount-in-cents, reference y signature:integrity.
- Firma de integridad: SHA256("<Referencia><MontoEnCentavos><Moneda><SecretoIntegridad>").
- Eventos: checksum = SHA256(valores de signature.properties en orden + timestamp
  + secreto de eventos); se compara con signature.checksum o el encabezado
  X-Event-Checksum. Wompi espera HTTP 200.
- Consulta de transacciones: solo con la llave privada (prv_...) desde el backend.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from urllib.parse import urlencode

import httpx

from config import cfg

log = logging.getLogger("portal.wompi")

CHECKOUT_URL = "https://checkout.wompi.co/p/"
API = {"sandbox": "https://sandbox.wompi.co/v1", "production": "https://production.wompi.co/v1"}
ESTADOS = {"APPROVED": "aprobado", "DECLINED": "rechazado", "VOIDED": "anulado", "ERROR": "error",
           "PENDING": "pendiente"}
MONEDA = "COP"


def configurado() -> bool:
    return cfg.wompi_configurado


def nueva_referencia(user_id: str) -> str:
    return f"PT-{user_id.replace('-', '')[:8]}-{secrets.token_hex(6)}".upper()


def firma_integridad(referencia: str, monto_centavos: int, moneda: str = MONEDA,
                     secreto: str | None = None, expiracion: str | None = None) -> str:
    cadena = f"{referencia}{monto_centavos}{moneda}{expiracion or ''}{secreto if secreto is not None else cfg.wompi_integrity_secret}"
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest()


def url_checkout(referencia: str, monto_centavos: int, email: str | None = None) -> str:
    params = {
        "public-key": cfg.wompi_public_key,
        "currency": MONEDA,
        "amount-in-cents": str(monto_centavos),
        "reference": referencia,
        "signature:integrity": firma_integridad(referencia, monto_centavos),
    }
    if cfg.wompi_redirect_url:
        params["redirect-url"] = cfg.wompi_redirect_url
    if email:
        params["customer-data:email"] = email
    return CHECKOUT_URL + "?" + urlencode(params, safe=":")


def _valor(evento: dict, propiedad: str):
    actual = evento.get("data") or {}
    for parte in propiedad.split("."):
        if not isinstance(actual, dict):
            return None
        actual = actual.get(parte)
    return actual


def checksum_evento(evento: dict, secreto: str | None = None) -> str:
    firma = evento.get("signature") or {}
    cadena = "".join(str(_valor(evento, p)) for p in firma.get("properties") or [])
    cadena += str(evento.get("timestamp", ""))
    cadena += secreto if secreto is not None else cfg.wompi_events_secret
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest()


def evento_valido(evento: dict, encabezado: str | None = None, secreto: str | None = None) -> bool:
    secreto = secreto if secreto is not None else cfg.wompi_events_secret
    if not secreto:
        return False
    recibido = (encabezado or (evento.get("signature") or {}).get("checksum") or "").strip().lower()
    if not recibido or not (evento.get("signature") or {}).get("properties"):
        return False
    return hmac.compare_digest(checksum_evento(evento, secreto).lower(), recibido)


def consultar_por_referencia(referencia: str) -> dict | None:
    """Transacción más relevante de una referencia (aprobada si la hay; si no, la más reciente).

    Sirve para el botón "Ya pagué, verificar" cuando el webhook no puede llegar
    (por ejemplo, con el backend corriendo en un PC sin dirección pública).
    """
    if not cfg.wompi_private_key:
        return None
    base = API.get(cfg.wompi_env, API["sandbox"])
    try:
        r = httpx.get(f"{base}/transactions", params={"reference": referencia},
                      headers={"Authorization": f"Bearer {cfg.wompi_private_key}"}, timeout=20)
    except httpx.HTTPError as exc:
        log.warning("No se pudo consultar Wompi: %s", type(exc).__name__)
        return None
    if r.status_code != 200:
        log.warning("Wompi respondió %s al consultar %s", r.status_code, referencia)
        return None
    datos = r.json().get("data") or []
    if isinstance(datos, dict):
        datos = [datos]
    datos = [t for t in datos if t.get("reference") == referencia]
    if not datos:
        return None
    aprobadas = [t for t in datos if t.get("status") == "APPROVED"]
    if aprobadas:
        return aprobadas[0]
    return sorted(datos, key=lambda t: t.get("created_at") or "", reverse=True)[0]
