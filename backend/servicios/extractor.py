"""Validación de archivos subidos y extracción de texto (PDF con pdfplumber, Word con python-docx)."""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from collections import Counter

from config import MAX_ARCHIVO
from errores import ErrorApi

TIPOS_MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "png": "image/png",
    "jpg": "image/jpeg",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def nombre_seguro(nombre: str, maximo: int = 80) -> str:
    """Quita tildes, rutas y caracteres raros de un nombre de archivo."""
    nombre = (nombre or "archivo").replace("\\", "/").split("/")[-1]
    nombre = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    nombre = re.sub(r"[^\w.\-]+", "_", nombre).strip("._") or "archivo"
    if len(nombre) > maximo:
        base, _, ext = nombre.rpartition(".")
        nombre = (base[:maximo - len(ext) - 1] + "." + ext) if base else nombre[:maximo]
    return nombre


def _es_docx(contenido: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            return "word/document.xml" in z.namelist()
    except zipfile.BadZipFile:
        return False


def _es_xlsx(contenido: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            return "xl/workbook.xml" in z.namelist()
    except zipfile.BadZipFile:
        return False


def tipo_real(contenido: bytes) -> str | None:
    if contenido.startswith(b"%PDF"):
        return "pdf"
    if contenido.startswith(b"PK\x03\x04"):
        if _es_docx(contenido):
            return "docx"
        if _es_xlsx(contenido):
            return "xlsx"
        return None
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if contenido.startswith(b"\xff\xd8\xff"):
        return "jpg"
    return None


def validar_archivo(nombre: str, contenido: bytes, permitidos: set[str]) -> str:
    """Revisa tamaño, tipo real y extensión. Devuelve el tipo ('pdf', 'docx', ...)."""
    if not contenido:
        raise ErrorApi(400, "archivo_vacio", "El archivo está vacío.")
    if len(contenido) > MAX_ARCHIVO:
        raise ErrorApi(413, "archivo_muy_grande", "El archivo supera el máximo de 20 MB.")
    ext = (nombre or "").lower().rsplit(".", 1)[-1] if "." in (nombre or "") else ""
    ext = "jpg" if ext == "jpeg" else ext
    if ext == "doc":
        raise ErrorApi(415, "formato_no_soportado",
                       "Los archivos .doc antiguos no se pueden leer. Guárdalo como .docx o PDF desde Word.")
    tipo = tipo_real(contenido)
    if tipo is None or tipo not in permitidos:
        legibles = ", ".join(sorted(x.upper() for x in permitidos))
        raise ErrorApi(415, "formato_no_soportado", f"Formato no permitido. Sube un archivo {legibles}.")
    if ext and ext != tipo:
        raise ErrorApi(415, "extension_no_coincide",
                       f"La extensión .{ext} no corresponde al contenido real del archivo ({tipo.upper()}).")
    return tipo


def _quitar_repetidas(paginas: list[str]) -> list[str]:
    """Quita líneas que se repiten en todas las páginas (encabezados y pies)."""
    if len(paginas) < 2:
        return paginas
    conteo = Counter()
    for p in paginas:
        conteo.update({l.strip() for l in p.splitlines() if l.strip()})
    repetidas = {l for l, n in conteo.items() if n >= len(paginas)}
    return ["\n".join(l for l in p.splitlines() if l.strip() not in repetidas) for p in paginas]


def texto_pdf(contenido: bytes) -> str:
    import pdfplumber

    paginas = []
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            # x_tolerance bajo: los PDF justificados juntan palabras con el valor por defecto
            paginas.append(pagina.extract_text(x_tolerance=1.5) or "")
    return "\n".join(_quitar_repetidas(paginas)).strip()


def texto_docx(contenido: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(contenido))
    partes: list[str] = []
    cuerpo = doc.element.body
    for el in cuerpo.iterchildren():
        etiqueta = el.tag.rsplit("}", 1)[-1]
        if etiqueta == "p":
            texto = "".join(t.text or "" for t in el.iter() if t.tag.endswith("}t"))
            if texto.strip():
                partes.append(texto)
        elif etiqueta == "tbl":
            for fila in el.iter():
                if fila.tag.endswith("}tr"):
                    celdas = []
                    for tc in fila.iterchildren():
                        if tc.tag.endswith("}tc"):
                            celdas.append(" ".join("".join(t.text or "" for t in p.iter() if t.tag.endswith("}t"))
                                                   for p in tc.iterchildren() if p.tag.endswith("}p")).strip())
                    linea = " | ".join(c for c in celdas if c)
                    if linea:
                        partes.append(linea)
    return "\n".join(partes).strip()


def extraer_texto(nombre: str, contenido: bytes) -> tuple[str, str]:
    """Devuelve (tipo, texto) de un PDF o Word, validando el archivo."""
    tipo = validar_archivo(nombre, contenido, {"pdf", "docx"})
    try:
        texto = texto_pdf(contenido) if tipo == "pdf" else texto_docx(contenido)
    except Exception as exc:
        raise ErrorApi(422, "archivo_ilegible",
                       "No pudimos leer el archivo. Revisa que no esté dañado ni protegido con contraseña.") from exc
    if len(texto) < 200:
        raise ErrorApi(422, "sin_texto",
                       "El archivo casi no tiene texto (¿es un escaneo?). Sube la versión digital de la minuta.")
    return tipo, texto
