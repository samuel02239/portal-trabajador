"""Indicador de carga: ícono girando + texto. Se usa mientras una tarea corre en segundo plano."""
import qtawesome as qta
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from app import tema


class Indicador(QWidget):
    def __init__(self, texto: str = "Cargando…", parent=None):
        super().__init__(parent)
        capa = QHBoxLayout(self)
        capa.setContentsMargins(0, 4, 0, 4)
        capa.setSpacing(10)
        self._boton = QPushButton()  # qtawesome anima íconos sobre un widget
        self._boton.setFlat(True)
        self._boton.setStyleSheet("border: none; background: transparent;")
        self._boton.setFocusPolicy(Qt.NoFocus)
        self._boton.setIconSize(QSize(20, 20))
        self._animacion = qta.Spin(self._boton)
        self._boton.setIcon(qta.icon("fa6s.spinner", color=tema.ACTUAL["enlace"], animation=self._animacion))
        self.texto = QLabel(texto)
        self.texto.setProperty("rol", "secundario")
        capa.addWidget(self._boton)
        capa.addWidget(self.texto, 1)
        self.setAccessibleName(texto)
        self.hide()

    def mostrar(self, texto: str | None = None) -> None:
        if texto:
            self.texto.setText(texto)
            self.setAccessibleName(texto)
        self.show()

    def ocultar(self) -> None:
        self.hide()
