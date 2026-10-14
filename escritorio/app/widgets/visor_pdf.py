"""Vista previa del PDF dentro del programa (QPdfView)."""
import tempfile
from pathlib import Path

from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app import config
from app.widgets import icono


class VisorPdf(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.documento = QPdfDocument(self)
        self.vista = QPdfView(self)
        self.vista.setDocument(self.documento)
        self.vista.setPageMode(QPdfView.PageMode.MultiPage)
        self.vista.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.vista.setMinimumHeight(420)
        self.vista.setAccessibleName("Vista previa del informe")
        self._archivo: Path | None = None

        barra = QHBoxLayout()
        self.info = QLabel("")
        self.info.setProperty("rol", "secundario")
        menos = QPushButton(icono("fa6s.magnifying-glass-minus"), "")
        menos.setAccessibleName("Alejar")
        menos.setToolTip("Alejar")
        mas = QPushButton(icono("fa6s.magnifying-glass-plus"), "")
        mas.setAccessibleName("Acercar")
        mas.setToolTip("Acercar")
        ajustar = QPushButton("Ajustar al ancho")
        menos.clicked.connect(lambda: self._zoom(0.8))
        mas.clicked.connect(lambda: self._zoom(1.25))
        ajustar.clicked.connect(lambda: self.vista.setZoomMode(QPdfView.ZoomMode.FitToWidth))
        barra.addWidget(self.info, 1)
        barra.addWidget(menos)
        barra.addWidget(mas)
        barra.addWidget(ajustar)

        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.addLayout(barra)
        capa.addWidget(self.vista, 1)

    def _zoom(self, factor: float) -> None:
        self.vista.setZoomMode(QPdfView.ZoomMode.Custom)
        self.vista.setZoomFactor(max(0.3, min(4.0, self.vista.zoomFactor() * factor)))

    def cargar(self, contenido: bytes) -> bool:
        config.CARPETA_CACHE.mkdir(parents=True, exist_ok=True)
        self.documento.close()
        if self._archivo and self._archivo.exists():
            try:
                self._archivo.unlink()
            except OSError:
                pass
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir=config.CARPETA_CACHE)
        f.write(contenido)
        f.close()
        self._archivo = Path(f.name)
        ok = self.documento.load(str(self._archivo)) == QPdfDocument.Error.None_
        self.info.setText(f"{self.documento.pageCount()} página(s)" if ok else "No se pudo mostrar el PDF.")
        return ok

    def limpiar(self) -> None:
        self.documento.close()
        self.info.setText("")
