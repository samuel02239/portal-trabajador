"""Preparación de fotos para pegarlas en el informe."""
from __future__ import annotations

import io
import logging

log = logging.getLogger("portal.imagenes")


def es_grande(jpeg: bytes, ancho: int, alto: int, origen: str = "foto") -> bool:
    """Decide si la imagen necesita una hoja completa (True) o cabe con otra (False).

    Grandes: páginas de documentos, imágenes verticales y capturas de pantalla o escaneos (fondo claro con
    texto), porque a la mitad de hoja no se leerían. Pequeñas: fotos apaisadas normales.
    """
    if origen == "documento":
        return True
    if alto > ancho * 1.2:
        return True
    try:
        from PIL import Image
        muestra = Image.open(io.BytesIO(jpeg)).convert("L")
        muestra.thumbnail((96, 96))
        hist = muestra.histogram()
        claros = sum(hist[225:]) / max(sum(hist), 1)
        return claros >= 0.55  # mayoría de fondo blanco: texto, tablas, pantallazos
    except Exception:
        return False


def preparar(contenido: bytes, lado_max: int = 1600) -> tuple[bytes, int, int] | None:
    """Endereza según EXIF (fotos de celular), reduce el tamaño y convierte a JPEG.

    Devuelve (jpeg, ancho_px, alto_px) o None si la imagen no se puede leer.
    """
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(contenido))
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            rgba = img.convert("RGBA")
            fondo = Image.new("RGB", rgba.size, (255, 255, 255))
            fondo.paste(rgba, mask=rgba.split()[-1])
            img = fondo
        img = img.convert("RGB")
        img.thumbnail((lado_max, lado_max))
        salida = io.BytesIO()
        img.save(salida, "JPEG", quality=82, optimize=True)
        return salida.getvalue(), img.width, img.height
    except Exception as exc:  # imagen dañada o formato raro: queda listada en ANEXOS, pero no se pega
        log.warning("No se pudo preparar una imagen: %s", type(exc).__name__)
        return None
