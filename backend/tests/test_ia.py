"""Respaldo entre modelos de OpenRouter (Fase 3: si se apaga el primer modelo, responde el segundo)."""
import dataclasses
import json

import httpx
import pytest
import respx

import ia
from schemas import ClasificacionIA

RESPUESTA_OK = {
    "asignaciones": [{"obligacion_numero": 1, "confianza": 0.92,
                      "redaccion": "Realicé el mantenimiento a los computadores de la oficina.",
                      "justificacion": "Es soporte técnico a equipos."}],
    "sin_coincidencia": False, "pregunta_aclaracion": None,
}


def _chat(contenido: str, modelo: str = "m"):
    return {"model": modelo, "choices": [{"message": {"content": contenido}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20}}


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setattr(ia, "cfg", dataclasses.replace(ia.cfg, openrouter_api_keys=("sk-prueba",)))
    ia._PAUSAS.clear()
    monkeypatch.setattr(ia, "proveedores_ia", lambda: [{"name": "Primero", "model": "uno/modelo"},
                                                       {"name": "Segundo", "model": "dos/modelo"}])
    monkeypatch.setattr(ia.time, "sleep", lambda s: None)
    registros = []
    monkeypatch.setattr(ia, "_registrar", lambda *a: registros.append(a))
    return registros


def _modelo(request) -> str:
    return json.loads(request.content)["model"]


@respx.mock
def test_si_el_primero_falla_responde_el_segundo(entorno):
    def responder(request):
        if _modelo(request) == "uno/modelo":
            return httpx.Response(503, json={"error": "caído"})
        return httpx.Response(200, json=_chat(json.dumps(RESPUESTA_OK)))

    respx.post(ia.API_URL).mock(side_effect=responder)
    resultado, nombre = ia.llamar_ia("clasificar_actividad", [{"role": "user", "content": "x"}], ClasificacionIA)
    assert nombre == "Segundo"
    assert resultado.asignaciones[0].obligacion_numero == 1
    # 3 intentos del primero (1 + 2 reintentos) y 1 del segundo, todos registrados
    assert [r[2] for r in entorno] == ["uno/modelo"] * 3 + ["dos/modelo"]
    assert [r[3] for r in entorno] == [False, False, False, True]


@respx.mock
def test_json_invalido_se_corrige_una_vez(entorno):
    llamadas = []

    def responder(request):
        llamadas.append(json.loads(request.content))
        if len(llamadas) == 1:
            return httpx.Response(200, json=_chat('{"asignaciones": [], "sin_coincidencia": false}'))
        return httpx.Response(200, json=_chat("```json\n" + json.dumps(RESPUESTA_OK) + "\n```"))

    respx.post(ia.API_URL).mock(side_effect=responder)
    resultado, nombre = ia.llamar_ia("clasificar_actividad", [{"role": "user", "content": "x"}], ClasificacionIA)
    assert nombre == "Primero" and len(llamadas) == 2
    assert "no cumple el esquema" in llamadas[1]["messages"][-1]["content"]


@respx.mock
def test_todos_fallan_lanza_iaerror():
    respx.post(ia.API_URL).mock(return_value=httpx.Response(400, json={"error": "modelo no existe"}))
    with pytest.raises(ia.IAError):
        ia.llamar_ia("clasificar_actividad", [{"role": "user", "content": "x"}], ClasificacionIA)


def test_sin_llave(monkeypatch):
    monkeypatch.setattr(ia, "cfg", dataclasses.replace(ia.cfg, openrouter_api_keys=()))
    with pytest.raises(ia.IANoConfigurada):
        ia.llamar_ia("x", [], ClasificacionIA)


@respx.mock
def test_si_una_llave_falla_usa_la_siguiente_y_la_pausa(monkeypatch, entorno):
    monkeypatch.setattr(ia, "cfg", dataclasses.replace(ia.cfg, openrouter_api_keys=("sk-sin-saldo", "sk-buena")))
    usadas = []

    def responder(request):
        llave = request.headers["Authorization"].split()[-1]
        usadas.append(llave)
        if llave == "sk-sin-saldo":
            return httpx.Response(402, json={"error": {"code": 402, "message": "Insufficient credits"}})
        return httpx.Response(200, json=_chat(json.dumps(RESPUESTA_OK)))

    respx.post(ia.API_URL).mock(side_effect=responder)
    resultado, nombre = ia.llamar_ia("clasificar_actividad", [{"role": "user", "content": "x"}], ClasificacionIA)
    assert nombre == "Primero" and usadas == ["sk-sin-saldo", "sk-buena"]
    # La llave sin saldo queda en pausa: la siguiente llamada va directo a la buena
    ia.llamar_ia("clasificar_actividad", [{"role": "user", "content": "x"}], ClasificacionIA)
    assert usadas[-1] == "sk-buena" and usadas.count("sk-sin-saldo") == 1
    assert ia.estado_llaves() == {"total": 2, "disponibles": 1}
    assert entorno[0][-1] == "sk-sin-saldo"  # se registra qué llave falló (en ia_logs se guarda solo el final)


@respx.mock
def test_todas_las_llaves_invalidas(monkeypatch):
    monkeypatch.setattr(ia, "cfg", dataclasses.replace(ia.cfg, openrouter_api_keys=("sk-1", "sk-2")))
    respx.post(ia.API_URL).mock(return_value=httpx.Response(401, json={"error": "No auth credentials found"}))
    with pytest.raises(ia.IAError) as e:
        ia.llamar_ia("clasificar_actividad", [{"role": "user", "content": "x"}], ClasificacionIA)
    assert "ninguna llave" in str(e.value)


def test_varias_llaves_en_una_variable(monkeypatch):
    import config
    monkeypatch.setenv("OPENROUTER_API_KEYS", "sk-a, sk-b\nsk-c")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-b")
    assert config.cargar().openrouter_api_keys == ("sk-a", "sk-b", "sk-c")
    assert ia.llave_visible("sk-or-v1-abcdef12345") == "…12345"


def test_confianza_en_porcentaje_se_normaliza():
    r = ClasificacionIA.model_validate({"asignaciones": [
        {"obligacion_numero": "2", "confianza": 45, "redaccion": "Asistí a la reunión."},
        {"obligacion_numero": 1, "confianza": "0.9", "redaccion": "Realicé soporte."}]})
    assert [a.obligacion_numero for a in r.asignaciones] == [1, 2]  # ordenadas por confianza
    assert r.asignaciones[1].confianza == 0.45


def test_niveles_de_confianza():
    from servicios.clasificador import nivel
    assert nivel(0.92) == "alta"
    assert nivel(0.75) == "alta"
    assert nivel(0.6) == "media"
    assert nivel(0.44) == "baja"
    assert nivel(0.9, sin_coincidencia=True) == "baja"
