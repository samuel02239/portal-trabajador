"""Insignia de estado: confirmada, propuesta, sin obligación (y niveles de confianza)."""
from PySide6.QtWidgets import QLabel

from app.widgets import refrescar_estilo

TEXTOS = {"confirmada": "Confirmada", "propuesta": "Propuesta", "sin_obligacion": "Sin obligación",
          "alta": "Confianza alta", "media": "Revisar", "baja": "No encaja"}


class Insignia(QLabel):
    def __init__(self, estado: str = "neutra", texto: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("insignia")
        self.poner(estado, texto)

    def poner(self, estado: str, texto: str | None = None) -> None:
        self.setProperty("estado", estado)
        self.setText(texto or TEXTOS.get(estado, estado))
        self.setAccessibleName(f"Estado: {self.text()}")
        refrescar_estilo(self)
