"""Cliente del backend: errores uniformes, renovación del token y falta de conexión (backend simulado con respx)."""
import httpx
import pytest
import respx

from app.servicios.api_cliente import ClienteApi
from app.servicios.errores import ErrorApp

BASE = "http://api.prueba"


@respx.mock
def test_error_402_trae_codigo_y_datos(gestor):
    respx.post(f"{BASE}/api/informes/i1/generar").mock(return_value=httpx.Response(402, json={"error": {
        "codigo": "limite_alcanzado", "mensaje": "Ya usaste los 2 informes de tu plan.", "usados": 2, "limite": 2}}))
    api = ClienteApi(BASE, gestor)
    with pytest.raises(ErrorApp) as e:
        api.generar_informe("i1", "parcial", "2026-10-31")
    assert e.value.status == 402 and e.value.codigo == "limite_alcanzado"
    assert e.value.datos == {"usados": 2, "limite": 2}
    assert "2 informes" in str(e.value)


@respx.mock
def test_401_renueva_token_y_repite(gestor):
    ruta = respx.get(f"{BASE}/api/contratos/actual").mock(side_effect=[
        httpx.Response(401, json={"error": {"codigo": "sesion_vencida", "mensaje": "x"}}),
        httpx.Response(200, json={"contrato": None, "obligaciones": []}),
    ])
    api = ClienteApi(BASE, gestor)
    assert api.contrato_actual() == {"contrato": None, "obligaciones": []}
    assert gestor.renovaciones == 1
    assert ruta.calls[0].request.headers["Authorization"] == "Bearer t1"
    assert ruta.calls[1].request.headers["Authorization"] == "Bearer t2"


@respx.mock
def test_sin_conexion(gestor):
    respx.get(f"{BASE}/api/suscripcion/actual").mock(side_effect=httpx.ConnectError("caído"))
    with pytest.raises(ErrorApp) as e:
        ClienteApi(BASE, gestor).suscripcion()
    assert e.value.codigo == "sin_conexion"
    assert "internet" in str(e.value)


@respx.mock
@pytest.mark.parametrize("modo,esperado", [("remoto", "iniciar_todo.bat"), ("integrado", "ábrelo de nuevo")])
def test_backend_local_apagado_dice_como_encenderlo(gestor, monkeypatch, modo, esperado):
    from app import config
    monkeypatch.setattr(config, "MODO_BACKEND", modo)
    respx.get("http://127.0.0.1:8000/api/suscripcion/actual").mock(side_effect=httpx.ConnectError("rechazada"))
    with pytest.raises(ErrorApp) as e:
        ClienteApi("http://127.0.0.1:8000", gestor).suscripcion()
    assert esperado in str(e.value)


@respx.mock
def test_clasificar_envia_texto_y_fecha(gestor):
    ruta = respx.post(f"{BASE}/api/actividades/clasificar").mock(return_value=httpx.Response(200, json={
        "asignaciones": [], "sin_coincidencia": True, "pregunta_aclaracion": None, "nivel": "baja"}))
    ClienteApi(BASE, gestor).clasificar("hoy hice mantenimiento", "2026-10-08")
    assert ruta.calls[0].request.content == b'{"texto":"hoy hice mantenimiento","fecha":"2026-10-08"}'
