"""Preparación de fotos para pegarlas en el informe."""
from __future__ import annotations

import io
import logging

log = logging.getLogger("portal.imagenes")


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
