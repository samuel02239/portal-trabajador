"""Pagos con Wompi: checkout, consulta de estado y webhook firmado (sección 13)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Request

from auth import Usuario, usuario_actual
from config import cfg
from db import get_db
from errores import ErrorApi, no_encontrado
from schemas import CheckoutEntrada
from servicios import cupo, pasarela_wompi as wompi

log = logging.getLogger("portal.pagos")
router = APIRouter(tags=["pagos"])

MENSAJES = {
    "pendiente": "Esperando la confirmación del pago…",
    "aprobado": "Pago aprobado. Tu plan quedó activado.",
    "rechazado": "El pago fue rechazado. Puedes intentarlo de nuevo con otro medio de pago.",
    "anulado": "El pago fue anulado. Puedes intentarlo de nuevo.",
    "error": "La pasarela reportó un error con el pago. Puedes intentarlo de nuevo.",
}


def _procesar(transaccion: dict, evento: dict) -> dict:
    """Aplica una transacción de Wompi (ya verificada) sobre la tabla pagos."""
    estado = wompi.ESTADOS.get(transaccion.get("status") or "", "pendiente")
    if estado == "pendiente":
        return {"ok": True, "estado": "pendiente"}
    if (transaccion.get("currency") or "COP") != wompi.MONEDA:
        return {"ok": False, "motivo": "moneda_no_coincide"}
    return get_db().rpc("procesar_pago", {
        "p_referencia": transaccion.get("reference"), "p_estado": estado,
        "p_id_transaccion": transaccion.get("id"),
        "p_monto_centavos": int(transaccion.get("amount_in_cents") or -1), "p_evento": evento})


@router.post("/pagos/checkout")
def crear_checkout(body: CheckoutEntrada, u: Usuario = Depends(usuario_actual)):
    if not wompi.configurado():
        raise ErrorApi(503, "pagos_no_configurados",
                       "Los pagos todavía no están habilitados. Intenta más tarde.")
    db = get_db()
    plan = db.uno("planes", {"id": body.plan_id, "activo": True})
    if not plan or plan["precio_cop"] <= 0:
        raise ErrorApi(400, "plan_invalido", "Ese plan no está disponible para pago.")
    referencia = wompi.nueva_referencia(u.id)
    db.insertar("pagos", {"user_id": u.id, "plan_id": plan["id"], "referencia": referencia,
                          "monto_cop": plan["precio_cop"], "estado": "pendiente", "pasarela": "wompi"})
    url = wompi.url_checkout(referencia, plan["precio_cop"] * 100, u.email or None)
    return {"referencia": referencia, "url": url, "plan_id": plan["id"], "monto_cop": plan["precio_cop"],
            "entorno": cfg.wompi_env}


@router.get("/pagos/{referencia}")
def estado_pago(referencia: str, u: Usuario = Depends(usuario_actual)):
    """Estado del pago. Si sigue pendiente, se consulta a Wompi con la llave privada (respaldo del webhook)."""
    db = get_db()
    pago = db.uno("pagos", {"referencia": referencia, "user_id": u.id})
    if not pago:
        raise no_encontrado("El pago")
    if pago["estado"] == "pendiente":
        transaccion = wompi.consultar_por_referencia(referencia)
        if transaccion:
            r = _procesar(transaccion, {"origen": "consulta", "transaction": transaccion})
            if not r.get("ok"):
                log.warning("Consulta de pago %s rechazada: %s", referencia, r.get("motivo"))
            pago = db.uno("pagos", {"referencia": referencia, "user_id": u.id})
    salida = {"referencia": pago["referencia"], "estado": pago["estado"], "plan_id": pago["plan_id"],
              "monto_cop": pago["monto_cop"], "mensaje": MENSAJES.get(pago["estado"], "")}
    if pago["estado"] == "aprobado":
        salida["suscripcion"] = cupo.estado(u.id)
    return salida


@router.post("/pagos/webhook")
async def webhook(request: Request, x_event_checksum: str | None = Header(default=None)):
    """Wompi notifica el resultado. Se valida la firma, la referencia y el monto; cada evento cuenta una vez."""
    try:
        evento = await request.json()
    except ValueError:
        raise ErrorApi(400, "evento_invalido", "Cuerpo inválido.")
    if not isinstance(evento, dict) or not wompi.evento_valido(evento, x_event_checksum):
        log.warning("Webhook con firma inválida")
        raise ErrorApi(401, "firma_invalida", "Firma inválida.")
    if evento.get("event") != "transaction.updated":
        return {"ok": True, "ignorado": evento.get("event")}
    esperado = "test" if cfg.wompi_env == "sandbox" else "prod"
    if evento.get("environment") and evento["environment"] != esperado:
        log.warning("Evento de otro entorno: %s", evento.get("environment"))
        return {"ok": True, "ignorado": "entorno"}
    transaccion = (evento.get("data") or {}).get("transaction") or {}
    r = _procesar(transaccion, evento)
    if not r.get("ok"):
        log.warning("Webhook rechazado (%s) para %s", r.get("motivo"), transaccion.get("reference"))
        raise ErrorApi(400, r.get("motivo") or "evento_rechazado", "Evento rechazado.")
    return {"ok": True, "estado": r.get("estado")}
