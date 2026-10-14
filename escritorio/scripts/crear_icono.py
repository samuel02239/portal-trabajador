"""Genera recursos/icono.png y recursos/icono.ico (ícono neutro: documento sobre verde azulado).

Uso:  python scripts/crear_icono.py
"""
import io
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

import qtawesome as qta  # noqa: E402
from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


def dibujar(tam: int) -> QImage:
    img = QImage(tam, tam, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#0A3D3D"))
    p.drawRoundedRect(QRectF(0, 0, tam, tam), tam * 0.18, tam * 0.18)
    margen = int(tam * 0.2)
    qta.icon("fa6s.file-lines", color="#E9E4D8").paint(p, margen, margen, tam - 2 * margen, tam - 2 * margen)
    p.end()
    return img


def a_pil(img: QImage) -> Image.Image:
    buf = QBuffer()
    buf.open(QBuffer.ReadWrite)
    img.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


def main():
    QApplication.instance() or QApplication(sys.argv)
    destino = BASE / "recursos"
    destino.mkdir(exist_ok=True)
    grande = a_pil(dibujar(256))
    grande.save(destino / "icono.png")
    grande.save(destino / "icono.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Ícono creado en", destino)


if __name__ == "__main__":
    main()
