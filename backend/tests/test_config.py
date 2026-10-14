"""Revisión de la configuración al desplegar y límite de solicitudes por usuario."""
import dataclasses

import pytest

import config
from errores import ErrorApi
from servicios import limites


def _cfg(**cambios):
    base = dataclasses.replace(
        config.cfg, supabase_url="https://x.supabase.co", supabase_anon_key="sb_publishable_x",
        supabase_service_key="sb_secret_x", openrouter_api_keys=("sk-1",), wompi_env="sandbox",
        wompi_public_key="", wompi_private_key="", wompi_events_secret="", wompi_integrity_secret="")
    return dataclasses.replace(base, **cambios)


WOMPI_PRUEBAS = dict(wompi_public_key="pub_test_a", wompi_private_key="prv_test_b",
                     wompi_events_secret="test_events_c", wompi_integrity_secret="test_integrity_d")


def test_configuracion_correcta_sin_avisos():
    assert config.revisar(_cfg()) == []
    assert config.revisar(_cfg(**WOMPI_PRUEBAS)) == []


def test_llaves_de_prueba_con_entorno_de_produccion():
    avisos = config.revisar(_cfg(wompi_env="production", **WOMPI_PRUEBAS))
    assert len(avisos) == 4
    assert any("pub_prod_" in a for a in avisos) and any("prod_integrity_" in a for a in avisos)
    assert not any(v in a for a in avisos for v in WOMPI_PRUEBAS.values())  # nunca muestra el valor de la llave


def test_no_cobra_si_las_llaves_son_de_otro_ambiente():
    assert _cfg(**WOMPI_PRUEBAS).wompi_configurado
    produccion = dict(wompi_public_key="pub_prod_a", wompi_private_key="prv_prod_b",
                      wompi_events_secret="prod_events_c", wompi_integrity_secret="prod_integrity_d")
    assert not _cfg(**produccion).wompi_configurado                       # llaves reales con WOMPI_ENV=sandbox
    assert _cfg(wompi_env="production", **produccion).wompi_configurado
    assert not _cfg(wompi_env="production", **WOMPI_PRUEBAS).wompi_configurado


def test_falta_una_llave_de_wompi():
    assert config.revisar(_cfg(wompi_public_key="pub_test_a")) == [
        "Falta WOMPI_PRIVATE_KEY.", "Falta WOMPI_EVENTS_SECRET.", "Falta WOMPI_INTEGRITY_SECRET."]


def test_llave_publica_de_supabase_en_lugar_de_la_secreta():
    assert any("sb_secret_" in a for a in config.revisar(_cfg(supabase_service_key="sb_publishable_x")))


@pytest.mark.parametrize("escrito,esperado", [("Produccion", "production"), ("producción", "production"),
                                              ("pruebas", "sandbox"), ("", "sandbox")])
def test_entorno_wompi_en_espanol(monkeypatch, escrito, esperado):
    monkeypatch.setenv("WOMPI_ENV", escrito)
    assert config.cargar().wompi_env == esperado


def test_entorno_wompi_desconocido_se_avisa(monkeypatch):
    monkeypatch.setenv("WOMPI_ENV", "real")
    assert any("WOMPI_ENV debe ser" in a for a in config.revisar(config.cargar()))


class _BaseFalsa:
    def __init__(self, respuesta=None, falla=False):
        self.respuesta, self.falla, self.llamadas = respuesta, falla, []

    def rpc(self, funcion, params):
        self.llamadas.append((funcion, params))
        if self.falla:
            raise ConnectionError("sin red")
        return self.respuesta


def test_limite_en_la_base_de_datos(monkeypatch):
    base = _BaseFalsa({"ok": False, "espera_s": 125})
    monkeypatch.setattr(limites, "get_db", lambda: base)
    with pytest.raises(ErrorApi) as e:
        limites.verificar("u1", "generar", 30)
    assert e.value.status == 429 and "3 minutos" in e.value.mensaje
    assert base.llamadas == [("registrar_solicitud", {"p_user": "u1", "p_accion": "generar",
                                                      "p_maximo": 30, "p_ventana_s": 3600})]
    monkeypatch.setattr(limites, "get_db", lambda: _BaseFalsa({"ok": True}))
    limites.verificar("u1", "generar", 30)  # con cupo no pasa nada


def test_sin_base_de_datos_cuenta_en_memoria(monkeypatch):
    monkeypatch.setattr(limites, "get_db", lambda: _BaseFalsa(falla=True))
    limites._REGISTRO.clear()
    limites.verificar("u2", "evidencia", 2)
    limites.verificar("u2", "evidencia", 2)
    with pytest.raises(ErrorApi):
        limites.verificar("u2", "evidencia", 2)
