"""Firma de integridad, validación de eventos y webhook de Wompi."""
import dataclasses
import hashlib

import pytest
from fastapi.testclient import TestClient

from servicios import pasarela_wompi as wompi

SECRETO_EVENTOS = "test_events_secreto"


def _evento(estado="APPROVED", monto=1000000, referencia="PT-REF-1", secreto=SECRETO_EVENTOS):
    ev = {
        "event": "transaction.updated",
        "data": {"transaction": {"id": "1234-1610641025-49201", "amount_in_cents": monto, "reference": referencia,
                                 "currency": "COP", "status": estado}},
        "environment": "test",
        "signature": {"properties": ["transaction.id", "transaction.status", "transaction.amount_in_cents"]},
        "timestamp": 1530291411,
    }
    ev["signature"]["checksum"] = wompi.checksum_evento(ev, secreto).upper()
    return ev


def test_firma_integridad_concatena_en_orden():
    esperado = hashlib.sha256(
        b"sk8-438k4-xmxm392-sn2m2490000COPprod_integrity_Z5mMke9x0k8gpErbDqwrJXMqsI6SFli6").hexdigest()
    assert wompi.firma_integridad("sk8-438k4-xmxm392-sn2m", 2490000, "COP",
                                  "prod_integrity_Z5mMke9x0k8gpErbDqwrJXMqsI6SFli6") == esperado


def test_checksum_de_evento():
    ev = _evento()
    cadena = "1234-1610641025-49201APPROVED10000001530291411" + SECRETO_EVENTOS
    assert ev["signature"]["checksum"] == hashlib.sha256(cadena.encode()).hexdigest().upper()
    assert wompi.evento_valido(ev, secreto=SECRETO_EVENTOS)
    adulterado = _evento()
    adulterado["data"]["transaction"]["amount_in_cents"] = 100
    assert not wompi.evento_valido(adulterado, secreto=SECRETO_EVENTOS)
    assert not wompi.evento_valido(_evento(secreto="otro"), secreto=SECRETO_EVENTOS)


class _DBFalsa:
    def __init__(self):
        self.pagos = {"PT-REF-1": {"monto_cop": 10000, "estado": "pendiente", "activaciones": 0}}

    def rpc(self, funcion, p):  # imita public.procesar_pago
        assert funcion == "procesar_pago"
        pago = self.pagos.get(p["p_referencia"])
        if not pago:
            return {"ok": False, "motivo": "referencia_desconocida"}
        if pago["monto_cop"] * 100 != p["p_monto_centavos"]:
            return {"ok": False, "motivo": "monto_no_coincide"}
        if pago["estado"] == "aprobado":
            return {"ok": True, "estado": "aprobado", "duplicado": True}
        pago["estado"] = p["p_estado"]
        if p["p_estado"] == "aprobado":
            pago["activaciones"] += 1
        return {"ok": True, "estado": p["p_estado"]}


@pytest.fixture
def app_wompi(monkeypatch):
    import main
    from routers import pagos

    cfg = dataclasses.replace(wompi.cfg, wompi_events_secret=SECRETO_EVENTOS, wompi_env="sandbox")
    monkeypatch.setattr(wompi, "cfg", cfg)
    monkeypatch.setattr(pagos, "cfg", cfg)
    db = _DBFalsa()
    monkeypatch.setattr(pagos, "get_db", lambda: db)
    return TestClient(main.app), db


def test_webhook_aprobado_una_sola_vez(app_wompi):
    cliente, db = app_wompi
    ev = _evento()
    assert cliente.post("/api/pagos/webhook", json=ev).status_code == 200
    assert cliente.post("/api/pagos/webhook", json=ev).status_code == 200  # el mismo evento repetido
    assert db.pagos["PT-REF-1"]["estado"] == "aprobado"
    assert db.pagos["PT-REF-1"]["activaciones"] == 1


def test_webhook_firma_invalida_no_cambia_nada(app_wompi):
    cliente, db = app_wompi
    r = cliente.post("/api/pagos/webhook", json=_evento(secreto="falso"))
    assert r.status_code == 401 and r.json()["error"]["codigo"] == "firma_invalida"
    assert db.pagos["PT-REF-1"]["estado"] == "pendiente"


def test_webhook_monto_o_referencia_distintos(app_wompi):
    cliente, db = app_wompi
    assert cliente.post("/api/pagos/webhook", json=_evento(monto=500)).status_code == 400
    assert cliente.post("/api/pagos/webhook", json=_evento(referencia="OTRA")).status_code == 400
    assert db.pagos["PT-REF-1"]["estado"] == "pendiente"


def test_webhook_rechazado_no_activa(app_wompi):
    cliente, db = app_wompi
    assert cliente.post("/api/pagos/webhook", json=_evento(estado="DECLINED")).status_code == 200
    assert db.pagos["PT-REF-1"]["estado"] == "rechazado" and db.pagos["PT-REF-1"]["activaciones"] == 0


def test_url_checkout(monkeypatch):
    monkeypatch.setattr(wompi, "cfg", dataclasses.replace(wompi.cfg, wompi_public_key="pub_test_x",
                                                          wompi_integrity_secret="test_integrity_y",
                                                          wompi_redirect_url=""))
    url = wompi.url_checkout("PT-1", 1000000, "a@b.co")
    assert url.startswith("https://checkout.wompi.co/p/?public-key=pub_test_x")
    assert "amount-in-cents=1000000" in url and "signature:integrity=" in url
    assert wompi.firma_integridad("PT-1", 1000000) in url
