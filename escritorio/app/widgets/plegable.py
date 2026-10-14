"""Sección plegable (acordeón) para Mi informe."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from app.widgets import icono


class SeccionPlegable(QFrame):
    def __init__(self, titulo: str, abierta: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("tarjeta")
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(0)
        self.cabecera_fila = QHBoxLayout()
        self.cabecera_fila.setContentsMargins(0, 0, 12, 0)
        self.cabecera = QToolButton()
        self.cabecera.setObjectName("cabeceraSeccion")
        self.cabecera.setText(titulo)
        self.cabecera.setCheckable(True)
        self.cabecera.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.cabecera.setIconSize(QSize(14, 14))
        self.cabecera.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.cabecera.toggled.connect(self._alternar)
        self.cabecera_fila.addWidget(self.cabecera, 1)
        capa.addLayout(self.cabecera_fila)
        self.cuerpo = QWidget()
        self.capa = QVBoxLayout(self.cuerpo)
        self.capa.setContentsMargins(16, 4, 16, 14)
        self.capa.setSpacing(10)
        capa.addWidget(self.cuerpo)
        self.cabecera.setChecked(abierta)
        self._alternar(abierta)

    def agregar_a_cabecera(self, widget) -> None:
        self.cabecera_fila.addWidget(widget, 0, Qt.AlignVCenter)

    def _alternar(self, abierta: bool) -> None:
        self.cuerpo.setVisible(abierta)
        self.cabecera.setIcon(icono("fa6s.chevron-down" if abierta else "fa6s.chevron-right"))
        self.cabecera.setAccessibleDescription("Abierta" if abierta else "Cerrada")
