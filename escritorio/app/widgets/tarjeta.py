"""Tarjeta y panel centrado."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget


class Tarjeta(QFrame):
    def __init__(self, titulo: str | None = None, subtitulo: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("tarjeta")
        self.capa = QVBoxLayout(self)
        self.capa.setContentsMargins(24, 20, 24, 20)
        self.capa.setSpacing(12)
        if titulo:
            t = QLabel(titulo)
            t.setProperty("rol", "subtitulo")
            t.setWordWrap(True)
            self.capa.addWidget(t)
        if subtitulo:
            s = QLabel(subtitulo)
            s.setProperty("rol", "secundario")
            s.setWordWrap(True)
            self.capa.addWidget(s)

    def agregar(self, widget, estirar: int = 0):
        self.capa.addWidget(widget, estirar)
        return widget


class PanelCentrado(QWidget):
    """Pone una tarjeta de ancho fijo (480 px por defecto) en el centro de la página, con desplazamiento."""

    def __init__(self, ancho: int = 480, parent=None):
        super().__init__(parent)
        self.setObjectName("fondo")
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        contenedor = QWidget()
        contenedor.setObjectName("contenidoScroll")
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(24, 32, 24, 32)
        self.tarjeta = Tarjeta()
        self.tarjeta.setFixedWidth(ancho)
        columna = QVBoxLayout()
        columna.addStretch(1)
        columna.addWidget(self.tarjeta)
        columna.addStretch(2)
        fila.addStretch(1)
        fila.addLayout(columna)
        fila.addStretch(1)
        scroll.setWidget(contenedor)
        externo.addWidget(scroll)

    @property
    def capa(self):
        return self.tarjeta.capa


class PanelMarca(QFrame):
    """Columna de marca para las pantallas de acceso: nombre, mensaje y puntos clave."""

    def __init__(self, titulo: str, texto: str, puntos: list[tuple[str, str]], pie: str = "", parent=None):
        super().__init__(parent)
        import qtawesome as qta

        self.setObjectName("panelMarca")
        capa = QVBoxLayout(self)
        capa.setContentsMargins(56, 48, 56, 40)
        capa.setSpacing(0)
        cabecera = QHBoxLayout()
        cuadro = QFrame()
        cuadro.setObjectName("marcaIcono")
        cuadro.setFixedSize(44, 44)
        ci = QVBoxLayout(cuadro)
        ci.setContentsMargins(0, 0, 0, 0)
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setPixmap(qta.icon("fa6s.file-lines", color="#FFFFFF").pixmap(22, 22))
        ci.addWidget(logo)
        nombre = QLabel("Portal del Trabajador")
        nombre.setStyleSheet("font-size: 13pt; font-weight: 600; color: #FFFFFF;")
        cabecera.addWidget(cuadro)
        cabecera.addSpacing(10)
        cabecera.addWidget(nombre)
        cabecera.addStretch(1)
        capa.addLayout(cabecera)
        capa.addStretch(2)
        t = QLabel(titulo)
        t.setProperty("rol", "marcaGrande")
        t.setWordWrap(True)
        d = QLabel(texto)
        d.setProperty("rol", "marcaTexto")
        d.setWordWrap(True)
        capa.addWidget(t)
        capa.addSpacing(14)
        capa.addWidget(d)
        capa.addSpacing(32)
        for icono, linea in puntos:
            fila = QHBoxLayout()
            fila.setSpacing(14)
            i = QLabel()
            i.setFixedWidth(26)
            i.setPixmap(qta.icon(icono, color="#5FC3D6").pixmap(20, 20))
            l = QLabel(linea)
            l.setWordWrap(True)
            l.setProperty("rol", "marcaTexto")
            fila.addWidget(i, 0, Qt.AlignTop)
            fila.addWidget(l, 1)
            capa.addLayout(fila)
            capa.addSpacing(16)
        capa.addStretch(3)
        if pie:
            p = QLabel(pie)
            p.setProperty("rol", "marcaPie")
            p.setWordWrap(True)
            capa.addWidget(p)


class PaginaDividida(QWidget):
    """Panel de marca a la izquierda y una tarjeta centrada a la derecha (acceso y primer ingreso)."""

    def __init__(self, marca: PanelMarca, ancho: int = 440, parent=None):
        super().__init__(parent)
        self.setObjectName("fondo")
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(0)
        fila.addWidget(marca, 5)
        derecha = PanelCentrado(ancho)
        derecha.setObjectName("ladoFormulario")
        derecha.tarjeta.setObjectName("formulario")  # el formulario va directo sobre el lado blanco
        contenido = derecha.findChild(QWidget, "contenidoScroll")
        contenido.setObjectName("vistaFormulario")
        contenido.setAttribute(Qt.WA_StyledBackground, True)
        fila.addWidget(derecha, 6)
        self.tarjeta = derecha.tarjeta
        self.capa = derecha.capa


class PaginaDesplazable(QWidget):
    """Página con margen y desplazamiento vertical, para las pantallas con barra lateral."""

    def __init__(self, ancho_max: int = 1000, parent=None):
        super().__init__(parent)
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        contenedor = QWidget()
        contenedor.setObjectName("contenidoScroll")
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(28, 24, 28, 28)
        interior = QWidget()
        interior.setMaximumWidth(ancho_max)
        self.capa = QVBoxLayout(interior)
        self.capa.setContentsMargins(0, 0, 0, 0)
        self.capa.setSpacing(16)
        self.capa.setAlignment(Qt.AlignTop)
        fila.addWidget(interior, 1)
        scroll.setWidget(contenedor)
        externo.addWidget(scroll)
