"""Reglas generales de la API: autenticación obligatoria, errores uniformes y validación de archivos."""
import pytest
from fastapi.testclient import TestClient

import main
from errores import ErrorApi
from servicios.extractor import nombre_seguro, validar_archivo


@pytest.fixture
def cliente():
    return TestClient(main.app)


def test_health_sin_token(cliente):
    r = cliente.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["Cache-Control"] == "no-store"


def test_pagina_de_correo_confirmado(cliente):
    r = cliente.get("/confirmado")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "correo quedó confirmado" in r.text and "default-src 'none'" in r.headers["Content-Security-Policy"]


def test_sin_documentacion_publica(cliente):
    assert cliente.get("/docs").status_code == 404 and cliente.get("/openapi.json").status_code == 404


@pytest.mark.parametrize("metodo,ruta", [
    ("get", "/api/contratos/actual"), ("post", "/api/actividades/clasificar"), ("get", "/api/informes/actual"),
    ("get", "/api/suscripcion/actual"), ("post", "/api/pagos/checkout"), ("delete", "/api/cuenta"),
])
def test_rutas_exigen_token(cliente, metodo, ruta):
    r = getattr(cliente, metodo)(ruta)
    assert r.status_code == 401
    assert set(r.json()["error"]) >= {"codigo", "mensaje"}


def test_validacion_de_archivos():
    with pytest.raises(ErrorApi) as e:
        validar_archivo("minuta.pdf", b"PK\x03\x04no-es-pdf", {"pdf"})
    assert e.value.status == 415
    with pytest.raises(ErrorApi) as e:
        validar_archivo("viejo.doc", b"\xd0\xcf\x11\xe0", {"pdf", "docx"})
    assert "docx" in e.value.mensaje
    with pytest.raises(ErrorApi) as e:
        validar_archivo("x.pdf", b"%PDF" + b"0" * (21 * 1024 * 1024), {"pdf"})
    assert e.value.status == 413
    assert validar_archivo("ok.pdf", b"%PDF-1.7 ...", {"pdf"}) == "pdf"


def test_nombre_seguro():
    assert nombre_seguro("..\\..\\Fotografía del evento (1).jpg") == "Fotografia_del_evento_1_.jpg"
    assert nombre_seguro("") == "archivo"
