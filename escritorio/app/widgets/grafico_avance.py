"""Avance por obligación en barras horizontales (una sola serie: un solo tono).

Cada fila tiene número y título (texto completo en la ayuda), la barra con el
extremo de datos redondeado y la base recta, la cantidad de actividades en
color de texto y, si no tiene ninguna, ícono + texto de alerta (nunca solo color).
"""
import qtawesome as qta
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QWidget

from app import tema
from app.widgets import mostrar_en


class _Barra(QWidget):
    def __init__(self, valor: int, maximo: int, parent=None):
        super().__init__(parent)
        self.valor, self.maximo = valor, max(1, maximo)
        self.setMinimumHeight(18)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, _):
        t = tema.ACTUAL
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        alto, radio = 10.0, 4.0
        y = (self.height() - alto) / 2
        p.setBrush(QColor(t["pista"]))
        p.drawRoundedRect(QRectF(0, y, self.width(), alto), radio, radio)
        if self.valor:
            ancho = max(radio * 2, self.width() * self.valor / self.maximo)
            camino = QPainterPath()
            camino.addRoundedRect(QRectF(0, y, ancho, alto), radio, radio)
            camino.addRect(QRectF(0, y, radio, alto))  # base recta, anclada al inicio
            p.setBrush(QColor(t["barra"]))
            p.drawPath(camino.simplified())
        p.end()


class _TituloElidido(QLabel):
    """Etiqueta que recorta con '…' cuando no cabe (el texto completo queda en la ayuda)."""

    def __init__(self, texto: str):
        super().__init__(texto)
        self.setMinimumWidth(160)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setPen(self.palette().color(self.foregroundRole()))
        texto = self.fontMetrics().elidedText(self.text(), Qt.ElideRight, self.width())
        p.drawText(self.rect(), int(Qt.AlignLeft | Qt.AlignVCenter), texto)
        p.end()


class GraficoAvance(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rejilla = QGridLayout(self)
        self.rejilla.setContentsMargins(0, 0, 0, 0)
        self.rejilla.setHorizontalSpacing(14)
        self.rejilla.setVerticalSpacing(10)
        self.rejilla.setColumnStretch(1, 3)
        self.rejilla.setColumnStretch(2, 3)

    def poner(self, obligaciones: list[dict]) -> None:
        """obligaciones: [{'numero', 'titulo_corto', 'texto', 'confirmadas'}]"""
        while self.rejilla.count():
            w = self.rejilla.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not obligaciones:
            vacio = QLabel("Tu contrato no tiene obligaciones específicas registradas.")
            vacio.setProperty("rol", "secundario")
            mostrar_en(self.rejilla, vacio, 0, 0, 1, 4)
            return
        maximo = max((o.get("confirmadas") or 0) for o in obligaciones) or 1
        for i, o in enumerate(obligaciones):
            n = o.get("confirmadas") or 0
            ayuda = f"Obligación {o['numero']}: {n} actividad{'es' if n != 1 else ''} confirmada{'s' if n != 1 else ''}\n\n{o['texto']}"
            numero = QLabel(str(o["numero"]))
            numero.setProperty("rol", "secundario")
            numero.setFixedWidth(22)
            numero.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            titulo = _TituloElidido(o.get("titulo_corto") or o["texto"][:40])
            barra = _Barra(n, maximo)
            cuenta = QLabel(str(n))
            cuenta.setStyleSheet("font-weight: 600;")
            cuenta.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            cuenta.setMinimumWidth(22)
            for w in (numero, titulo, barra, cuenta):
                w.setToolTip(ayuda)
            barra.setAccessibleName(f"Obligación {o['numero']}: {n} actividades")
            mostrar_en(self.rejilla, numero, i, 0)
            mostrar_en(self.rejilla, titulo, i, 1)
            mostrar_en(self.rejilla, barra, i, 2)
            mostrar_en(self.rejilla, cuenta, i, 3)
            estado = QWidget()
            fe = QHBoxLayout(estado)
            fe.setContentsMargins(0, 0, 0, 0)
            fe.setSpacing(6)
            if n == 0:
                alerta = QLabel()
                alerta.setPixmap(qta.icon("fa6s.triangle-exclamation", color=tema.ACTUAL["advertencia"]).pixmap(14, 14))
                texto = QLabel("Sin actividades")
                texto.setStyleSheet(f"color: {tema.ACTUAL['advertencia']}; font-weight: 600;")
                fe.addWidget(alerta)
                fe.addWidget(texto)
            fe.addStretch(1)
            estado.setMinimumWidth(130)
            mostrar_en(self.rejilla, estado, i, 4)
