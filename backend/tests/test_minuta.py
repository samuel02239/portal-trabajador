from pathlib import Path

import pytest

from conftest import MINUTA_TEXTO
from servicios import minuta

MINUTA_REAL = Path(__file__).resolve().parents[3] / "MINUTA-9681-SAMUEL ELIAS OLIVERA MIRANDA.pdf"


def test_divide_especificas_y_generales():
    esp_txt, gen_txt = minuta.localizar_clausulas(MINUTA_TEXTO)
    esp = minuta.dividir_numeradas(esp_txt)
    gen = minuta.dividir_numeradas(gen_txt)
    assert len(esp) == 4
    assert esp[0] == "REALIZAR SOPORTE TÉCNICO A LOS EQUIPOS TECNOLÓGICOS DE LA DEPENDENCIA"
    assert "LEY 1150 DE 2007" in esp[1]          # los números de leyes no parten la obligación
    assert esp[3] == "LAS DEMAS QUE LE SEAN ASIGNADAS."  # '..' final se normaliza
    # El "3." repetido se queda dentro de la obligación anterior; no se mezclan las del contratante
    assert len(gen) == 4
    assert "riesgos laborales" in gen[2]
    assert all("Pagar" not in g for g in gen)


def test_extraer_basico():
    b = minuta.extraer_basico(MINUTA_TEXTO)
    assert b["contrato"]["numero"] == "1234"
    assert b["contrato"]["valor_total"] == 3000000.0
    assert b["contratista"] == {"nombre": "PERSONA DE PRUEBA EJEMPLO", "cedula": "1000000001"}
    assert b["supervisor"]["cargo"] == "JEFE DE LA OFICINA DE PRUEBA"
    assert b["contrato"]["objeto"].startswith("PRESTACIÓN DE SERVICIOS")


def test_analizar_sin_ia_devuelve_lo_extraido(monkeypatch):
    from ia import IANoConfigurada

    def sin_ia(*a, **k):
        raise IANoConfigurada("sin llave")

    monkeypatch.setattr(minuta, "llamar_ia", sin_ia)
    r = minuta.analizar_minuta(MINUTA_TEXTO)
    assert len([o for o in r["datos"]["obligaciones"] if o["tipo"] == "especifica"]) == 4
    assert any("IA" in a for a in r["avisos"])


def test_analizar_con_ia_conserva_texto_del_documento(monkeypatch):
    from schemas import MinutaIA

    def ia_falsa(tarea, mensajes, esquema, **k):
        return MinutaIA.model_validate({
            "contrato": {"numero": "1234", "tipo_contratacion": "prestación de servicios"},
            "obligaciones": [{"numero": 1, "tipo": "especifica", "texto": "SOPORTE (resumido por la IA)",
                              "palabras_clave": ["soporte", "equipos"]}],
        }), "modelo-prueba"

    monkeypatch.setattr(minuta, "llamar_ia", ia_falsa)
    r = minuta.analizar_minuta(MINUTA_TEXTO)
    esp = [o for o in r["datos"]["obligaciones"] if o["tipo"] == "especifica"]
    assert len(esp) == 4 and esp[0]["texto"].startswith("REALIZAR SOPORTE")  # texto fiel del documento
    assert esp[0]["palabras_clave"] == ["soporte", "equipos"]
    assert r["modelo"] == "modelo-prueba"


@pytest.mark.skipif(not MINUTA_REAL.exists(), reason="minuta de ejemplo no disponible")
def test_minuta_de_ejemplo_tiene_10_especificas(monkeypatch):
    from servicios.extractor import extraer_texto
    from ia import IANoConfigurada

    monkeypatch.setattr(minuta, "llamar_ia", lambda *a, **k: (_ for _ in ()).throw(IANoConfigurada("x")))
    _, texto = extraer_texto("m.pdf", MINUTA_REAL.read_bytes())
    r = minuta.analizar_minuta(texto)
    esp = [o for o in r["datos"]["obligaciones"] if o["tipo"] == "especifica"]
    assert len(esp) == 10
    assert esp[0]["texto"].startswith("REALIZAR SOPORTE TÉCNICO A LOS EQUIPOS TECNOLÓGICOS")
    assert esp[9]["texto"].startswith("LAS DEMAS QUE LE SEAN ASIGNADAS")
