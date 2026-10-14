"""Contraste AA (sección 9.1) y generación del QSS desde los tokens."""
import pytest

from app import tema

PARES_TEXTO = [("texto", "fondo"), ("texto", "superficie"), ("texto", "superficie_alt"), ("texto_sec", "fondo"),
               ("texto_sec", "superficie"), ("texto_sec", "superficie_alt"), ("exito", "exito_fondo"),
               ("advertencia", "advertencia_fondo"), ("error", "error_fondo"), ("info", "info_fondo"),
               ("sobre_primario", "primario"), ("sobre_primario", "acento"), ("lateral_texto", "lateral"),
               ("lateral_texto", "lateral_activo"), ("lateral_sec", "lateral"), ("enlace", "superficie"),
               ("primario_txt", "superficie"), ("primario_txt", "primario_suave"), ("texto", "primario_suave"),
               ("error", "superficie")]
PARES_GRAFICOS = [("borde_fuerte", "campo"), ("barra", "superficie"), ("barra", "pista"), ("foco", "superficie")]


@pytest.mark.parametrize("nombre,tokens", [("claro", tema.CLARO), ("oscuro", tema.OSCURO)])
def test_contraste_aa(qapp, nombre, tokens):
    for a, b in PARES_TEXTO:
        assert tema.contraste(tokens[a], tokens[b]) >= 4.5, f"{nombre}: {a} sobre {b}"
    # Bordes de campos, barras del gráfico e íconos: contraste no textual ≥ 3:1
    for a, b in PARES_GRAFICOS:
        assert tema.contraste(tokens[a], tokens[b]) >= 3, f"{nombre}: {a} sobre {b}"
    from app.widgets import COLOR_ICONO
    assert tema.contraste(COLOR_ICONO, tokens["superficie"]) >= 3


def test_ambos_temas_tienen_los_mismos_tokens():
    assert set(tema.CLARO) == set(tema.OSCURO)


def test_qss_usa_los_tokens(qapp):
    hoja = tema.qss(tema.CLARO, "Segoe UI", "Georgia")
    assert tema.CLARO["primario"] in hoja and tema.CLARO["fondo"] in hoja
    assert f"font-size: {tema.TAM_BASE}pt" in hoja
