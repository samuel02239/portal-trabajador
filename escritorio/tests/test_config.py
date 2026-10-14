"""Configuración segura: https obligatorio hacia internet y aviso de versión antigua."""
import pytest

from app import config


def test_version_tupla():
    assert config.version_tupla("1.10.0") > config.version_tupla("1.9.3")
    assert config.version_tupla("1.1") == (1, 1)
    assert config.version_tupla("2.0.0-beta") == (2, 0, 0)


@pytest.mark.parametrize("modo,url,problema", [
    ("remoto", "http://api.ejemplo.com", True),          # internet sin cifrar: se rechaza
    ("remoto", "https://api.ejemplo.com", False),
    ("remoto", "http://127.0.0.1:8000", False),          # en el mismo PC sí se permite
    ("integrado", "http://api.ejemplo.com", False),
])
def test_https_obligatorio(monkeypatch, modo, url, problema):
    monkeypatch.setattr(config, "MODO_BACKEND", modo)
    monkeypatch.setattr(config, "API_BASE_URL", url)
    assert bool(config.problema_de_configuracion()) is problema


class _ApiDormida:
    """Servidor en la nube que tarda en despertar: falla unas veces y luego responde."""

    def __init__(self, fallas, error):
        self.fallas, self.error, self.llamadas = fallas, error, 0

    def health(self):
        self.llamadas += 1
        if self.llamadas <= self.fallas:
            raise self.error
        return {"ok": True}


def test_espera_al_servidor_que_esta_despertando(qapp, monkeypatch):
    from app.servicios.errores import ErrorApp
    from app.ventanas import principal
    monkeypatch.setattr(principal.time, "sleep", lambda s: None)
    monkeypatch.setattr(config, "MODO_BACKEND", "remoto")
    api = _ApiDormida(3, ErrorApp("tardó", "tiempo_agotado"))
    assert principal.VentanaPrincipal._salud(api) == {"ok": True} and api.llamadas == 4
    api = _ApiDormida(2, ErrorApp("Bad gateway", "error_http", 502))
    assert principal.VentanaPrincipal._salud(api) == {"ok": True}


def test_no_insiste_con_errores_que_no_son_de_conexion(qapp, monkeypatch):
    from app.servicios.errores import ErrorApp
    from app.ventanas import principal
    monkeypatch.setattr(principal.time, "sleep", lambda s: None)
    monkeypatch.setattr(config, "MODO_BACKEND", "remoto")
    api = _ApiDormida(5, ErrorApp("no autorizado", "error_http", 401))
    with pytest.raises(ErrorApp):
        principal.VentanaPrincipal._salud(api)
    assert api.llamadas == 1
    monkeypatch.setattr(config, "MODO_BACKEND", "integrado")  # el servidor interno no se espera
    api = _ApiDormida(5, ErrorApp("tardó", "sin_conexion"))
    with pytest.raises(ErrorApp):
        principal.VentanaPrincipal._salud(api)
    assert api.llamadas == 1


def test_version_antigua_avisa_con_enlace(qapp, monkeypatch):
    from app.servicios.errores import ErrorApp
    from app.ventanas.principal import VentanaPrincipal
    monkeypatch.setattr(config, "VERSION", "1.1.0")
    VentanaPrincipal._revisar_version({"escritorio": {"version_minima": "1.1.0"}})  # igual: no pasa nada
    with pytest.raises(ErrorApp) as e:
        VentanaPrincipal._revisar_version({"escritorio": {"version_minima": "1.2.0",
                                                          "url_descarga": "https://descargas.ejemplo/portal"}})
    assert e.value.codigo == "version_antigua" and "https://descargas.ejemplo/portal" in str(e.value)
