"""Reglas de la propuesta de la IA (sección 7.3) en la pantalla de actividad."""
from datetime import date

from app.ventanas.actividad import PanelPropuesta, nivel


def _asig(o, conf, texto="Realicé el mantenimiento a los computadores de la oficina."):
    return {"obligacion_id": o["id"], "obligacion_numero": o["numero"], "obligacion_texto": o["texto"],
            "confianza": conf, "redaccion": texto, "justificacion": "porque sí"}


def test_umbrales():
    assert nivel(0.92) == "alta" and nivel(0.75) == "alta"
    assert nivel(0.74) == "media" and nivel(0.45) == "media"
    assert nivel(0.44) == "baja" and nivel(None) == "baja"
    assert nivel(0.9, sin_coincidencia=True) == "baja"


def test_confianza_alta_lista_para_guardar(qtbot, obligaciones):
    p = PanelPropuesta()
    qtbot.addWidget(p)
    p.mostrar({"asignaciones": [_asig(obligaciones[0], 0.92)], "sin_coincidencia": False, "modelo": "m"},
              "hoy hice mantenimiento a los computadores", obligaciones)
    assert p.encaja.text() == "Encaja en: Obligación 1"
    assert p.confianza.text() == "Confianza: 92 %"
    datos = p.datos(date(2026, 10, 8))
    assert len(datos) == 1
    assert datos[0]["obligacion_id"] == "o1" and datos[0]["estado"] == "confirmada"
    assert datos[0]["texto_redactado"].startswith("Realicé el mantenimiento")
    assert datos[0]["confianza"] == 0.92 and datos[0]["fecha"] == "2026-10-08"


def test_confianza_media_muestra_dos_alternativas(qtbot, obligaciones):
    p = PanelPropuesta()
    qtbot.addWidget(p)
    asign = [_asig(obligaciones[0], 0.6), _asig(obligaciones[1], 0.55, "Otra redacción."),
             _asig(obligaciones[2], 0.5, "Tercera.")]
    p.mostrar({"asignaciones": asign, "sin_coincidencia": False}, "texto", obligaciones)
    assert "Revisa si es la obligación correcta" in p.banner.texto.text()
    botones = [p.alternativas.itemAt(i).widget() for i in range(p.alternativas.count())]
    assert sum(1 for b in botones if b and b.text().startswith("Usar obligación")) == 2
    p.usar(asign[1])
    assert p.combo.currentData() == "o2" and p.redaccion.toPlainText() == "Otra redacción."


def test_confianza_baja_queda_sin_obligacion(qtbot, obligaciones):
    p = PanelPropuesta()
    qtbot.addWidget(p)
    p.mostrar({"asignaciones": [_asig(obligaciones[0], 0.3)], "sin_coincidencia": False}, "fui al médico", obligaciones)
    assert "no parece estar entre tus obligaciones" in p.banner.texto.text()
    assert p.combo.currentData() is None
    assert p.datos(date(2026, 10, 8))[0]["estado"] == "sin_obligacion"
    # El usuario puede asignarla a mano
    p.combo.setCurrentIndex(p.combo.findData("o3"))
    d = p.datos(date(2026, 10, 8))[0]
    assert d["estado"] == "confirmada" and d["obligacion_id"] == "o3"


def test_varias_obligaciones_se_guardan_si_se_marcan(qtbot, obligaciones):
    p = PanelPropuesta()
    qtbot.addWidget(p)
    p.mostrar({"asignaciones": [_asig(obligaciones[0], 0.9), _asig(obligaciones[1], 0.8, "Segunda.")],
               "sin_coincidencia": False}, "texto", obligaciones)
    assert len(p.casillas_extra) == 1
    p.casillas_extra[0][0].setChecked(True)
    datos = p.datos(date(2026, 10, 8))
    assert [d["obligacion_id"] for d in datos] == ["o1", "o2"]
    assert datos[1]["texto_redactado"] == "Segunda."


def test_sin_ia_guarda_sin_clasificar(qtbot, obligaciones):
    p = PanelPropuesta()
    qtbot.addWidget(p)
    p.mostrar_manual("hice algo", obligaciones)
    d = p.datos(date(2026, 10, 8))[0]
    assert d["estado"] == "propuesta" and d["obligacion_id"] is None and d["texto_redactado"] == "hice algo"
