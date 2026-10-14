"""Capturas de página de documentos (PDF, Word, Excel) para pegarlas como imágenes en los anexos."""
from __future__ import annotations

import io
import logging

from servicios import conversor_pdf

log = logging.getLogger("portal.capturas")

MAX_PAGINAS = 12   # por documento; el resto se omite y se avisa
ESCALA = 1.6       # ~115 ppp: legible en el informe sin inflar el Word


def paginas(contenido: bytes, tipo: str, maximo: int = MAX_PAGINAS) -> tuple[list[bytes], int]:
    """Devuelve (JPEG de cada página, total de páginas del documento).

    tipo: 'pdf', 'docx' o 'xlsx'. Si no se puede convertir o leer, devuelve ([], 0).
    """
    pdf = contenido if tipo == "pdf" else conversor_pdf.convertir(contenido, extension=tipo)
    if not pdf:
        return [], 0
    try:
        import pypdfium2 as pdfium

        documento = pdfium.PdfDocument(pdf)
        try:
            total = len(documento)
            salida = []
            for i in range(min(total, maximo)):
                pagina = documento[i]
                try:
                    img = pagina.render(scale=ESCALA).to_pil().convert("RGB")
                finally:
                    pagina.close()
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=85, optimize=True)
                salida.append(buf.getvalue())
            return salida, total
        finally:
            documento.close()
    except Exception as exc:  # PDF protegido o dañado: el anexo queda como archivo adjunto
        log.warning("No se pudieron tomar las capturas del documento (%s): %s", tipo, type(exc).__name__)
        return [], 0
