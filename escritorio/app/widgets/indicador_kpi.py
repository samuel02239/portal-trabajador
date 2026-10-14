"""Indicador (tarjeta de un número): etiqueta, valor y una nota corta."""
import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from app import tema


class IndicadorKpi(QFrame):
    def __init__(self, etiqueta: str, icono: str, parent=None):
        super().__init__(parent)
        self.setObjectName("indicador")
        self.setMinimumWidth(180)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(18, 16, 18, 16)
        capa.setSpacing(4)
        fila = QHBoxLayout()
        self.etiqueta = QLabel(etiqueta)
        self.etiqueta.setProperty("rol", "kpiEtiqueta")
        self.icono = QLabel()
        self._icono = icono
        fila.addWidget(self.etiqueta, 1)
        fila.addWidget(self.icono, 0, Qt.AlignTop)
        self.valor = QLabel("—")
        self.valor.setProperty("rol", "kpiValor")
        self.nota = QLabel("")
        self.nota.setProperty("rol", "kpiNota")
        self.nota.setWordWrap(True)
        capa.addLayout(fila)
        capa.addWidget(self.valor)
        capa.addWidget(self.nota)
        self.pintar_icono()

    def pintar_icono(self, color: str | None = None) -> None:
        self.icono.setPixmap(qta.icon(self._icono, color=color or tema.ACTUAL["primario_txt"]).pixmap(18, 18))

    def poner(self, valor: str, nota: str = "", estado: str | None = None) -> None:
        """estado: None o 'advertencia' (el ícono cambia a color de advertencia; el texto lo explica)."""
        self.valor.setText(valor)
        self.nota.setText(nota)
        self.pintar_icono(tema.ACTUAL["advertencia"] if estado == "advertencia" else None)
        self.setAccessibleName(f"{self.etiqueta.text()}: {valor}. {nota}")
