"""Medidor de informes restantes (por ejemplo, "Gratis · quedan 1 de 2").

Compacto: un chip para la barra superior. Normal: texto con barra, para la pantalla Generar.
"""
import qtawesome as qta
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from app import tema


def texto_cupo(s: dict | None) -> str:
    if not s:
        return "Plan: cargando…"
    if s.get("sin_limite") or s.get("plan") == "pruebas":
        return "Cuenta de pruebas · sin límite"
    nombre = "Gratis" if s.get("plan") == "gratis" else s.get("plan_nombre") or s.get("plan", "").capitalize()
    if s.get("limite") is None:
        return f"Plan {nombre} · informes ilimitados"
    restantes = s.get("restantes") or 0
    periodo = "" if s.get("periodo_limite") == "total" else " este mes"
    return f"Plan {nombre} · quedan {restantes} de {s['limite']}{periodo}"


class MedidorCupo(QWidget):
    def __init__(self, compacto: bool = True, parent=None):
        super().__init__(parent)
        self.compacto = compacto
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        if compacto:
            self.marco = QFrame()
            self.marco.setObjectName("chip")
            fila = QHBoxLayout(self.marco)
            fila.setContentsMargins(12, 5, 14, 5)
            fila.setSpacing(8)
            self.icono = QLabel()
            fila.addWidget(self.icono)
            col = QVBoxLayout()
            col.setSpacing(3)
            self.etiqueta = QLabel(texto_cupo(None))
            self.barra = QProgressBar()
            self.barra.setTextVisible(False)
            self.barra.setFixedHeight(4)
            col.addWidget(self.etiqueta)
            col.addWidget(self.barra)
            fila.addLayout(col)
            externo.addWidget(self.marco)
        else:
            externo.setSpacing(6)
            self.icono = None
            self.etiqueta = QLabel(texto_cupo(None))
            self.etiqueta.setProperty("rol", "seccion")
            self.barra = QProgressBar()
            self.barra.setTextVisible(False)
            externo.addWidget(self.etiqueta)
            externo.addWidget(self.barra)

    def poner(self, s: dict | None) -> None:
        texto = texto_cupo(s)
        self.etiqueta.setText(texto)
        self.setAccessibleName(texto)
        ilimitado = bool(s) and s.get("limite") is None
        if ilimitado:
            self.barra.hide()
        else:
            self.barra.show()
            self.barra.setRange(0, max(1, (s or {}).get("limite") or 1))
            self.barra.setValue((s or {}).get("restantes") or 0)
        if self.icono is not None:
            nombre = "fa6s.infinity" if ilimitado else "fa6s.file-circle-check"
            self.icono.setPixmap(qta.icon(nombre, color=tema.ACTUAL["primario_txt"]).pixmap(16, 16))
        self.setToolTip("Informes que todavía puedes generar con tu plan.")
