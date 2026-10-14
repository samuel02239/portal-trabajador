"""Zona para arrastrar y soltar un archivo (o elegirlo con clic / Enter)."""
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QFrame, QLabel, QVBoxLayout

from app import config, tema
from app.widgets import refrescar_estilo


class ZonaArchivo(QFrame):
    archivo_elegido = Signal(str)
    archivo_invalido = Signal(str)

    def __init__(self, texto: str = "Arrastra tu archivo aquí", extensiones: tuple[str, ...] = (".pdf", ".docx"),
                 parent=None):
        super().__init__(parent)
        self.setObjectName("zonaArchivo")
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(150)
        self.extensiones = tuple(e.lower() for e in extensiones)
        self.ruta: str | None = None
        capa = QVBoxLayout(self)
        capa.setAlignment(Qt.AlignCenter)
        self.icono = QLabel()
        self.icono.setAlignment(Qt.AlignCenter)
        self.icono.setPixmap(qta.icon("fa6s.cloud-arrow-up", color=tema.ACTUAL["enlace"]).pixmap(36, 36))
        self.titulo = QLabel(texto)
        self.titulo.setAlignment(Qt.AlignCenter)
        self.titulo.setProperty("rol", "seccion")
        tipos = " o ".join(e.upper().lstrip(".") for e in self.extensiones)
        self.detalle = QLabel(f"({tipos}, máximo 20 MB) · o haz clic para buscarlo")
        self.detalle.setAlignment(Qt.AlignCenter)
        self.detalle.setProperty("rol", "secundario")
        self.detalle.setWordWrap(True)
        for w in (self.icono, self.titulo, self.detalle):
            capa.addWidget(w)
        self.setAccessibleName(f"{texto}. Pulsa Enter para buscar el archivo.")

    def _activar(self, si: bool) -> None:
        self.setProperty("activa", si)
        refrescar_estilo(self)

    def _validar(self, ruta: str) -> bool:
        p = Path(ruta)
        if p.suffix.lower() not in self.extensiones:
            self.archivo_invalido.emit(f"Ese tipo de archivo no sirve. Usa {', '.join(self.extensiones)}.")
            return False
        if not p.is_file():
            self.archivo_invalido.emit("No se encontró el archivo.")
            return False
        if p.stat().st_size > config.MAX_ARCHIVO:
            self.archivo_invalido.emit("El archivo supera el máximo de 20 MB.")
            return False
        return True

    def _elegir(self, ruta: str) -> None:
        if self._validar(ruta):
            self.ruta = ruta
            self.titulo.setText(Path(ruta).name)
            self.detalle.setText("Archivo listo · haz clic para cambiarlo")
            self.archivo_elegido.emit(ruta)

    def buscar(self) -> None:
        filtro = "Archivos (" + " ".join(f"*{e}" for e in self.extensiones) + ")"
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegir archivo", "", filtro)
        if ruta:
            self._elegir(ruta)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.buscar()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.buscar()
        else:
            super().keyPressEvent(e)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._activar(True)

    def dragLeaveEvent(self, e):
        self._activar(False)

    def dropEvent(self, e):
        self._activar(False)
        urls = e.mimeData().urls()
        if urls:
            self._elegir(urls[0].toLocalFile())
