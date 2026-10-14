"""Componentes: medidor de cupo, campos y validación del inicio de sesión."""
from datetime import date

from app.widgets.campos import CampoFecha
from app.widgets.medidor_cupo import MedidorCupo, texto_cupo


def test_texto_cupo():
    assert texto_cupo({"plan": "gratis", "limite": 2, "restantes": 1, "periodo_limite": "total"}) == \
        "Plan Gratis · quedan 1 de 2"
    assert texto_cupo({"plan": "normal", "plan_nombre": "Normal", "limite": 2, "restantes": 0,
                       "periodo_limite": "mensual"}) == "Plan Normal · quedan 0 de 2 este mes"
    assert texto_cupo({"plan": "pro", "plan_nombre": "Pro", "limite": None}) == "Plan Pro · informes ilimitados"


def test_medidor(qtbot):
    m = MedidorCupo()
    qtbot.addWidget(m)
    m.poner({"plan": "gratis", "limite": 2, "restantes": 1, "periodo_limite": "total"})
    assert m.barra.maximum() == 2 and m.barra.value() == 1


def test_campo_fecha_opcional(qtbot):
    f = CampoFecha("Fecha de inicio")
    qtbot.addWidget(f)
    assert f.fecha() is None and f.iso() is None
    f.poner("2026-10-01")
    assert f.fecha() == date(2026, 10, 1)
    f.poner(None)
    assert f.fecha() is None


def test_login_valida_campos(qtbot, monkeypatch):
    from app.ventanas.login import VentanaLogin

    class VentanaFalsa:
        def iniciar_con(self, sesion):
            raise AssertionError("no debía intentar entrar")

    w = VentanaLogin(VentanaFalsa())
    qtbot.addWidget(w)
    w.b_crear.click()
    w.nombre.poner("Ana")
    w.correo.poner("no-es-correo")
    w.clave.poner("123")
    assert w._validar() is False
    assert w.nombre.mensaje.text() and w.correo.mensaje.text() and w.clave.mensaje.text()
    assert "tratamiento" in w.aviso.texto.text()
    w.nombre.poner("Ana María Pérez")
    w.correo.poner("ana@ejemplo.com")
    w.clave.poner("ClaveSegura1")
    w.acepto.setChecked(True)
    assert w._validar() is True
