"""Aviso en línea (info, éxito, advertencia, error): siempre con color, ícono y texto."""
import qtawesome as qta
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from app import tema
from app.widgets import icono, refrescar_estilo

ICONOS = {"info": "fa6s.circle-info", "exito": "fa6s.circle-check",
          "advertencia": "fa6s.triangle-exclamation", "error": "fa6s.circle-exclamation"}
PREFIJOS = {"info": "Información", "exito": "Listo", "advertencia": "Atención", "error": "Error"}


class Aviso(QFrame):
    accion = Signal()

    def __init__(self, texto: str = "", nivel: str = "info", cerrable: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("aviso")
        capa = QHBoxLayout(self)
        capa.setContentsMargins(12, 10, 12, 10)
        capa.setSpacing(10)
        self.icono = QLabel()
        self.icono.setFixedSize(20, 20)
        self.texto = QLabel()
        self.texto.setWordWrap(True)
        self.texto.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.boton = QPushButton()
        self.boton.setProperty("variante", "enlace")
        self.boton.hide()
        self.boton.clicked.connect(self.accion.emit)
        capa.addWidget(self.icono, 0, Qt.AlignTop)
        capa.addWidget(self.texto, 1)
        capa.addWidget(self.boton, 0, Qt.AlignVCenter)
        if cerrable:
            cerrar = QPushButton()
            cerrar.setProperty("variante", "enlace")
            cerrar.setIcon(icono("fa6s.xmark"))
            cerrar.setIconSize(QSize(14, 14))
            cerrar.setAccessibleName("Cerrar aviso")
            cerrar.clicked.connect(self.hide)
            capa.addWidget(cerrar, 0, Qt.AlignTop)
        self.mostrar(texto, nivel) if texto else self.hide()

    def mostrar(self, texto: str, nivel: str = "info", accion: str | None = None) -> None:
        self.setProperty("nivel", nivel)
        self.icono.setPixmap(qta.icon(ICONOS[nivel], color=tema.ACTUAL[nivel]).pixmap(20, 20))
        self.texto.setText(texto)
        self.setAccessibleName(f"{PREFIJOS[nivel]}: {texto}")
        if accion:
            self.boton.setText(accion)
            self.boton.show()
        else:
            self.boton.hide()
        refrescar_estilo(self)
        self.show()

    def ocultar(self) -> None:
        self.hide()
