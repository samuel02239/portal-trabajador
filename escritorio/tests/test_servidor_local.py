"""El programa enciende el backend integrado en un hilo, responde /api/health y se apaga al cerrar."""
import httpx
import pytest

from app import config
from app.servicios import servidor_local


@pytest.mark.skipif(config.carpeta_backend() is None, reason="no está la carpeta del backend")
def test_enciende_y_apaga_el_backend_integrado():
    puerto = servidor_local._puerto_cualquiera()
    s = servidor_local.ServidorLocal()
    url = s.asegurar(puerto=puerto, reutilizar=False, espera=60)
    try:
        assert url == f"http://127.0.0.1:{puerto}"
        r = httpx.get(f"{url}/api/health", timeout=5)
        assert r.status_code == 200 and r.json()["servicio"] == "portal-trabajador"
        assert s.asegurar() == url  # llamarlo otra vez no enciende otro
    finally:
        s.detener()
    with pytest.raises(httpx.HTTPError):
        httpx.get(f"{url}/api/health", timeout=2)


def test_reutiliza_un_backend_que_ya_responde(monkeypatch):
    monkeypatch.setattr(servidor_local, "_responde", lambda url, timeout=1.5: True)
    s = servidor_local.ServidorLocal()
    assert s.asegurar(puerto=8123) == "http://127.0.0.1:8123"
    assert not s.propio  # no encendió nada propio
