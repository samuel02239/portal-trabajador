"""Sistema visual: todos los colores y tamaños viven aquí.

Cambiar un color es cambiarlo en un solo lugar. La hoja de estilo QSS se genera
a partir de estos valores; `python -m app.tema` la exporta a recursos/.

Paleta institucional: azul petróleo como color principal, grises fríos para
fondos y bordes, barra lateral azul marino. Cada par texto/fondo cumple
contraste AA (4.5:1) y los bordes de campos e íconos 3:1, en claro y oscuro
(lo comprueba tests/test_tema.py).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QPalette

CLARO = {
    # superficies
    "fondo": "#F3F5F8", "superficie": "#FFFFFF", "superficie_alt": "#F7F9FB", "campo": "#FFFFFF",
    # texto
    "texto": "#0F1B2D", "texto_sec": "#4A5A6E", "deshabilitado": "#8592A3",
    # bordes
    "borde": "#E2E7EE", "borde_boton": "#CBD3DD", "borde_fuerte": "#7D8A9B",
    # marca
    "primario": "#0E5A6B", "acento": "#0A4756", "sobre_primario": "#FFFFFF", "primario_suave": "#E6F1F4",
    "primario_txt": "#0E5A6B", "enlace": "#0B6478", "foco": "#1A7C93", "hover": "#F0F3F7",
    # barra lateral
    "lateral": "#0B1E2D", "lateral_texto": "#D3DCE6", "lateral_sec": "#93A4B6", "lateral_hover": "#132A3C",
    "lateral_activo": "#173449", "lateral_marca": "#5FC3D6",
    # gráficos (un solo tono; la pista es un paso más claro del mismo tono)
    "pista": "#E1EEF1", "barra": "#1F7A8C",
    # estados (siempre con ícono y texto)
    "exito": "#127A46", "exito_fondo": "#E8F6EE",
    "advertencia": "#8F5300", "advertencia_fondo": "#FFF5E3",
    "error": "#B42318", "error_fondo": "#FEF0EE",
    "info": "#0B6478", "info_fondo": "#E8F3F6",
}

OSCURO = {
    "fondo": "#0B111A", "superficie": "#121A26", "superficie_alt": "#162030", "campo": "#0E1520",
    "texto": "#E6EBF2", "texto_sec": "#9EACBC", "deshabilitado": "#6A788C",
    "borde": "#223044", "borde_boton": "#33445C", "borde_fuerte": "#66768C",
    "primario": "#12708A", "acento": "#158099", "sobre_primario": "#FFFFFF", "primario_suave": "#13303D",
    "primario_txt": "#86CFDF", "enlace": "#86CFDF", "foco": "#86CFDF", "hover": "#1A2536",
    "lateral": "#070D15", "lateral_texto": "#D3DCE6", "lateral_sec": "#8D9DB0", "lateral_hover": "#101B29",
    "lateral_activo": "#16283B", "lateral_marca": "#5FC3D6",
    "pista": "#1B3140", "barra": "#4FB3C8",
    "exito": "#6FD3A0", "exito_fondo": "#0F2A1C",
    "advertencia": "#F2B85B", "advertencia_fondo": "#33250D",
    "error": "#F59A90", "error_fondo": "#3A1612",
    "info": "#86CFDF", "info_fondo": "#0F2833",
}

RADIO = 6
TAM_BASE = 11       # pt, mínimo en toda la interfaz
TAM_TITULO = 21
TAM_SUBTITULO = 14
ICONO_MENU = 18     # px


def fuentes() -> tuple[str, str]:
    """(fuente de interfaz, fuente de títulos) disponibles en el equipo."""
    familias = set(QFontDatabase.families())
    ui = "Segoe UI" if "Segoe UI" in familias else ("Inter" if "Inter" in familias else "Sans Serif")
    titulos = next((f for f in ("Source Serif 4", "Source Serif 4 Semibold", "Georgia") if f in familias), "Serif")
    return ui, titulos


def tokens(oscuro: bool) -> dict:
    return OSCURO if oscuro else CLARO


def qss(t: dict, ui: str = "Segoe UI", titulos: str = "Georgia") -> str:
    r = RADIO
    return f"""
QWidget {{ color: {t['texto']}; font-family: "{ui}"; font-size: {TAM_BASE}pt; }}
QMainWindow, QDialog, QWidget#fondo, QStackedWidget#paginas {{ background: {t['fondo']}; }}
QScrollArea {{ background: transparent; border: none; }}
QWidget#contenidoScroll {{ background: transparent; }}

/* ---------- Tarjetas y contenedores ---------- */
QFrame#tarjeta {{ background: {t['superficie']}; border: 1px solid {t['borde']}; border-radius: {r + 2}px; }}
QFrame#indicador {{ background: {t['superficie']}; border: 1px solid {t['borde']}; border-radius: {r + 2}px; }}
QFrame#barraSuperior {{ background: {t['superficie']}; border-bottom: 1px solid {t['borde']}; }}
QFrame#separador {{ background: {t['borde']}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#chip {{ background: {t['primario_suave']}; border: 1px solid {t['borde']}; border-radius: 15px; }}
QFrame#chip QLabel {{ color: {t['primario_txt']}; font-weight: 600; background: transparent; }}
QLabel#avatar {{ background: {t['primario']}; color: {t['sobre_primario']}; border-radius: 17px; font-weight: 700;
    font-size: 10pt; }}

/* ---------- Barra lateral ---------- */
QFrame#barraLateral {{ background: {t['lateral']}; }}
QFrame#barraLateral QLabel {{ color: {t['lateral_texto']}; background: transparent; }}
QFrame#barraLateral QLabel[rol="lateralSec"] {{ color: {t['lateral_sec']}; font-size: 9pt; letter-spacing: 1px; }}
QFrame#barraLateral QLabel[rol="lateralMarca"] {{ font-family: "{titulos}"; font-size: 14pt; color: #FFFFFF; }}
QFrame#barraLateral QLabel[rol="lateralDato"] {{ color: {t['lateral_sec']}; }}
QFrame#marcaIcono {{ background: {t['primario']}; border-radius: {r}px; }}
QPushButton#navBoton {{ color: {t['lateral_texto']}; background: transparent; border: none; border-left: 3px solid transparent;
    border-radius: 0; padding: 10px 14px; text-align: left; font-size: {TAM_BASE}pt; }}
QPushButton#navBoton:hover {{ background: {t['lateral_hover']}; color: #FFFFFF; }}
QPushButton#navBoton:checked {{ background: {t['lateral_activo']}; color: #FFFFFF; font-weight: 600;
    border-left: 3px solid {t['lateral_marca']}; }}
QPushButton#navBoton:focus {{ background: {t['lateral_hover']}; border-left: 3px solid {t['lateral_marca']}; }}
QFrame#usuarioLateral {{ background: {t['lateral_hover']}; border-radius: {r}px; }}

/* ---------- Panel de marca (inicio de sesión) ---------- */
QWidget#ladoFormulario, QWidget#vistaFormulario {{ background: {t['superficie']}; }}
QFrame#formulario {{ background: transparent; border: none; }}
QFrame#panelMarca {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {t['lateral']}, stop:1 #0E3446); }}
QFrame#panelMarca QLabel {{ color: {t['lateral_texto']}; background: transparent; }}
QFrame#panelMarca QLabel[rol="marcaGrande"] {{ font-family: "{titulos}"; font-size: 28pt; color: #FFFFFF; }}
QFrame#panelMarca QLabel[rol="marcaTexto"] {{ font-size: 12pt; color: {t['lateral_texto']}; }}
QFrame#panelMarca QLabel[rol="marcaPie"] {{ font-size: 9pt; color: {t['lateral_sec']}; }}

/* ---------- Tipografía ---------- */
QLabel[rol="titulo"] {{ font-family: "{titulos}"; font-size: {TAM_TITULO}pt; color: {t['texto']}; }}
QLabel[rol="subtitulo"] {{ font-family: "{titulos}"; font-size: {TAM_SUBTITULO}pt; color: {t['texto']}; }}
QLabel[rol="marca"] {{ color: {t['texto_sec']}; }}
QLabel[rol="migas"] {{ color: {t['texto_sec']}; }}
QLabel[rol="migasActual"] {{ color: {t['texto']}; font-weight: 600; }}
QLabel[rol="seccion"] {{ font-weight: 600; }}
QLabel[rol="secundario"] {{ color: {t['texto_sec']}; }}
QLabel[rol="error"] {{ color: {t['error']}; }}
QLabel[rol="cita"] {{ color: {t['texto_sec']}; font-style: italic; }}
QLabel[rol="grande"] {{ font-size: 16pt; font-weight: 600; color: {t['primario_txt']}; }}
QLabel[rol="kpiValor"] {{ font-size: 22pt; font-weight: 600; color: {t['texto']}; }}
QLabel[rol="kpiEtiqueta"] {{ color: {t['texto_sec']}; }}
QLabel[rol="kpiNota"] {{ color: {t['texto_sec']}; }}
QLabel[rol="precio"] {{ font-size: 20pt; font-weight: 600; color: {t['texto']}; }}
QLabel a {{ color: {t['enlace']}; }}

/* ---------- Botones ---------- */
QPushButton {{ background: {t['superficie']}; color: {t['texto']}; border: 1px solid {t['borde_boton']};
    border-radius: {r}px; padding: 8px 16px; min-height: 22px; font-weight: 600; }}
QPushButton:hover {{ background: {t['hover']}; border-color: {t['borde_fuerte']}; }}
QPushButton:pressed {{ background: {t['borde']}; }}
QPushButton:focus {{ border: 2px solid {t['foco']}; }}
QPushButton:disabled {{ color: {t['deshabilitado']}; border-color: {t['borde']}; background: {t['superficie_alt']}; }}
QPushButton[variante="primario"] {{ background: {t['primario']}; color: {t['sobre_primario']}; border: 1px solid {t['primario']}; }}
QPushButton[variante="primario"]:hover {{ background: {t['acento']}; border-color: {t['acento']}; }}
QPushButton[variante="primario"]:focus {{ border: 2px solid {t['foco']}; }}
QPushButton[variante="primario"]:disabled {{ background: {t['borde']}; color: {t['deshabilitado']}; border-color: {t['borde']}; }}
QPushButton[variante="peligro"] {{ background: {t['superficie']}; color: {t['error']}; border: 1px solid {t['error']}; }}
QPushButton[variante="peligro"]:hover {{ background: {t['error_fondo']}; }}
QPushButton[variante="enlace"] {{ background: transparent; border: none; color: {t['enlace']}; padding: 2px 4px;
    font-weight: 600; min-height: 0; }}
QPushButton[variante="enlace"]:hover {{ text-decoration: underline; }}
QPushButton[variante="enlace"]:focus {{ border: 1px dashed {t['foco']}; }}
QPushButton[variante="icono"] {{ padding: 6px; min-width: 22px; background: transparent; border: 1px solid transparent; }}
QPushButton[variante="icono"]:hover {{ background: {t['hover']}; border-color: {t['borde_boton']}; }}
QPushButton[segmento="true"] {{ border-radius: 0; padding: 9px 12px; background: {t['superficie_alt']};
    color: {t['texto_sec']}; }}
QPushButton[segmento="true"]:checked {{ background: {t['superficie']}; color: {t['primario_txt']};
    border-bottom: 2px solid {t['primario']}; }}

/* ---------- Campos ---------- */
QLineEdit, QPlainTextEdit, QTextEdit, QDateEdit, QComboBox, QSpinBox {{ background: {t['campo']}; color: {t['texto']};
    border: 1px solid {t['borde_fuerte']}; border-radius: {r}px; padding: 7px 10px; font-size: {TAM_BASE}pt;
    selection-background-color: {t['primario']}; selection-color: #FFFFFF; }}
QLineEdit:hover, QPlainTextEdit:hover, QDateEdit:hover, QComboBox:hover {{ border-color: {t['texto_sec']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QDateEdit:focus, QComboBox:focus {{ border: 2px solid {t['foco']}; }}
QLineEdit[error="true"], QPlainTextEdit[error="true"], QDateEdit[error="true"], QComboBox[error="true"] {{ border: 2px solid {t['error']}; }}
QLineEdit:read-only {{ background: {t['superficie_alt']}; color: {t['texto_sec']}; border-color: {t['borde_boton']}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: {t['superficie']}; color: {t['texto']}; selection-background-color: {t['primario_suave']};
    selection-color: {t['texto']}; border: 1px solid {t['borde_boton']}; outline: 0; padding: 4px; }}
QCalendarWidget QWidget {{ background: {t['superficie']}; color: {t['texto']}; }}
QListWidget {{ background: {t['campo']}; border: 1px solid {t['borde_boton']}; border-radius: {r}px; padding: 4px; }}
QListWidget::item {{ padding: 4px; border-radius: 4px; }}
QListWidget::item:selected {{ background: {t['primario_suave']}; color: {t['texto']}; }}

/* ---------- Avisos ---------- */
QFrame#aviso {{ border-radius: {r}px; border: 1px solid; border-left: 4px solid; }}
QFrame#aviso[nivel="info"] {{ background: {t['info_fondo']}; border-color: {t['borde']}; border-left-color: {t['info']}; }}
QFrame#aviso[nivel="exito"] {{ background: {t['exito_fondo']}; border-color: {t['borde']}; border-left-color: {t['exito']}; }}
QFrame#aviso[nivel="advertencia"] {{ background: {t['advertencia_fondo']}; border-color: {t['borde']}; border-left-color: {t['advertencia']}; }}
QFrame#aviso[nivel="error"] {{ background: {t['error_fondo']}; border-color: {t['borde']}; border-left-color: {t['error']}; }}
QFrame#aviso QLabel {{ background: transparent; color: {t['texto']}; }}

/* ---------- Insignias ---------- */
QLabel#insignia {{ border-radius: 10px; padding: 2px 10px; font-weight: 600; }}
QLabel#insignia[estado="confirmada"], QLabel#insignia[estado="alta"] {{ background: {t['exito_fondo']}; color: {t['exito']}; }}
QLabel#insignia[estado="propuesta"], QLabel#insignia[estado="media"] {{ background: {t['advertencia_fondo']}; color: {t['advertencia']}; }}
QLabel#insignia[estado="sin_obligacion"], QLabel#insignia[estado="baja"] {{ background: {t['error_fondo']}; color: {t['error']}; }}
QLabel#insignia[estado="neutra"] {{ background: {t['superficie_alt']}; color: {t['texto_sec']}; border: 1px solid {t['borde']}; }}
QLabel#insignia[estado="marca"] {{ background: {t['primario_suave']}; color: {t['primario_txt']}; }}

/* ---------- Medidores ---------- */
QProgressBar {{ background: {t['pista']}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ background: {t['barra']}; border-radius: 3px; }}

/* ---------- Zona de archivo ---------- */
QFrame#zonaArchivo {{ background: {t['superficie_alt']}; border: 2px dashed {t['borde_fuerte']}; border-radius: {r + 2}px; }}
QFrame#zonaArchivo:hover {{ border-color: {t['foco']}; }}
QFrame#zonaArchivo[activa="true"] {{ border-color: {t['foco']}; background: {t['primario_suave']}; }}
QFrame#zonaArchivo:focus {{ border: 2px solid {t['foco']}; }}

QFrame#filaActividad {{ border: none; border-top: 1px solid {t['borde']}; background: transparent; }}

/* ---------- Acordeón ---------- */
QToolButton#cabeceraSeccion {{ background: transparent; border: none; padding: 12px 14px; text-align: left;
    font-weight: 600; font-size: {TAM_BASE}pt; color: {t['texto']}; }}
QToolButton#cabeceraSeccion:hover {{ color: {t['primario_txt']}; }}
QToolButton#cabeceraSeccion:focus {{ border: 2px solid {t['foco']}; border-radius: {r}px; }}

/* ---------- Tablas, menús y otros ---------- */
QTableWidget {{ background: {t['superficie']}; gridline-color: {t['borde']}; border: 1px solid {t['borde']};
    border-radius: {r}px; alternate-background-color: {t['superficie_alt']}; }}
QHeaderView::section {{ background: {t['superficie_alt']}; color: {t['texto_sec']}; padding: 8px; border: none;
    border-bottom: 1px solid {t['borde']}; font-weight: 600; }}
QToolTip {{ background: {t['texto']}; color: {t['superficie']}; border: none; padding: 6px 8px; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QMenu {{ background: {t['superficie']}; border: 1px solid {t['borde_boton']}; padding: 4px; }}
QMenu::item {{ padding: 7px 18px; border-radius: 4px; }}
QMenu::item:selected {{ background: {t['primario_suave']}; color: {t['texto']}; }}
QMenu::separator {{ height: 1px; background: {t['borde']}; margin: 4px 8px; }}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['borde_boton']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t['borde_fuerte']}; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t['borde_boton']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""


def paleta(t: dict) -> QPalette:
    p = QPalette()
    c = lambda k: QColor(t[k])  # noqa: E731
    p.setColor(QPalette.Window, c("fondo"))
    p.setColor(QPalette.WindowText, c("texto"))
    p.setColor(QPalette.Base, c("campo"))
    p.setColor(QPalette.AlternateBase, c("superficie_alt"))
    p.setColor(QPalette.Text, c("texto"))
    p.setColor(QPalette.Button, c("superficie"))
    p.setColor(QPalette.ButtonText, c("texto"))
    p.setColor(QPalette.Highlight, c("primario"))
    p.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    p.setColor(QPalette.ToolTipBase, c("texto"))
    p.setColor(QPalette.ToolTipText, c("superficie"))
    p.setColor(QPalette.PlaceholderText, c("texto_sec"))
    p.setColor(QPalette.Link, c("enlace"))
    for rol in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, rol, c("deshabilitado"))
    return p


def sistema_oscuro() -> bool:
    """Sigue la configuración de Windows (Qt 6.5+)."""
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        return False


def resolver(modo: str) -> bool:
    """modo: 'sistema' | 'claro' | 'oscuro'. Devuelve True si toca oscuro."""
    return sistema_oscuro() if modo == "sistema" else modo == "oscuro"


ACTUAL: dict = CLARO  # tokens del tema aplicado (para íconos y gráficos pintados a mano)


def aplicar(app, modo: str = "sistema") -> dict:
    global ACTUAL
    t = tokens(resolver(modo))
    ACTUAL = t
    app.setStyle("Fusion")
    app.setPalette(paleta(t))
    ui, titulos = fuentes()
    app.setStyleSheet(qss(t, ui, titulos))
    return t


def _luminancia(hex_color: str) -> float:
    c = QColor(hex_color)
    canales = []
    for v in (c.redF(), c.greenF(), c.blueF()):
        canales.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    r, g, b = canales
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def exportar() -> None:
    from app.config import RECURSOS
    RECURSOS.mkdir(exist_ok=True)
    (RECURSOS / "tema.qss").write_text(qss(CLARO), encoding="utf-8")
    (RECURSOS / "tema_oscuro.qss").write_text(qss(OSCURO), encoding="utf-8")


if __name__ == "__main__":
    exportar()
    print("QSS exportado a recursos/tema.qss y recursos/tema_oscuro.qss")
