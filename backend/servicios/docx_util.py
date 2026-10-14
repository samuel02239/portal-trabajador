"""Utilidades de bajo nivel sobre el XML de Word (WordprocessingML)."""
from __future__ import annotations

import copy
import re
import unicodedata

from lxml import etree

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "v": "urn:schemas-microsoft-com:vml",
    "xml": "http://www.w3.org/XML/1998/namespace",
}

# Etiquetas de control de cambios que no deben copiarse al formato de un run
_REVISIONES = {"ins", "del", "moveFrom", "moveTo", "rPrChange"}


def q(etiqueta: str) -> str:
    """'w:p' -> '{ns}p'."""
    prefijo, nombre = etiqueta.split(":")
    return f"{{{NS[prefijo]}}}{nombre}"


def normalizar(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", (s or "").replace("\xa0", " ")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def texto_de(el) -> str:
    """Texto visible del elemento, sin el contenido de cuadros de texto anidados."""
    partes = []
    for t in el.iter(q("w:t"), q("w:tab"), q("w:br")):
        dentro_de_caja = any(a.tag == q("w:txbxContent") for a in t.iterancestors())
        if dentro_de_caja and el.tag != q("w:txbxContent"):
            continue
        if t.tag == q("w:t"):
            partes.append(t.text or "")
        elif t.tag == q("w:tab"):
            partes.append("\t")
        else:
            partes.append("\n")
    return "".join(partes)


def parrafos_cuerpo(body) -> list:
    return [e for e in body.iterchildren() if e.tag == q("w:p")]


def tablas_cuerpo(body) -> list:
    return [e for e in body.iterchildren() if e.tag == q("w:tbl")]


def filas(tbl) -> list:
    return [e for e in tbl.iterchildren() if e.tag == q("w:tr")]


def celdas(tr) -> list:
    """Celdas reales de la fila (una celda combinada horizontalmente cuenta una vez)."""
    salida = []
    for e in tr.iterchildren():
        if e.tag == q("w:tc"):
            salida.append(e)
        elif e.tag == q("w:sdt"):  # celda dentro de un control de contenido
            salida += [tc for tc in e.iter(q("w:tc"))]
    return salida


def parrafos_de(tc) -> list:
    return [e for e in tc.iterchildren() if e.tag == q("w:p")]


def _runs(p) -> list:
    """Runs del párrafo, incluidos los que están dentro de hipervínculos o inserciones."""
    return [r for r in p.iter(q("w:r"))
            if not any(a.tag == q("w:txbxContent") for a in r.iterancestors())]


def limpiar_rpr(rpr):
    if rpr is None:
        return None
    rpr = copy.deepcopy(rpr)
    for hijo in list(rpr):
        if etree.QName(hijo).localname in _REVISIONES:
            rpr.remove(hijo)
    rpr.tag = q("w:rPr")
    return rpr


def rpr_de_parrafo(p):
    """Formato de letra que tendría un texto escrito en este párrafo.

    Orden: el primer run con texto; cualquier run; la marca de párrafo (pPr/rPr).
    """
    runs = _runs(p)
    for r in runs:
        if (texto_de(r) or "").strip(" ") and r.find(q("w:rPr")) is not None:
            return limpiar_rpr(r.find(q("w:rPr")))
    for r in runs:
        if r.find(q("w:rPr")) is not None:
            return limpiar_rpr(r.find(q("w:rPr")))
    ppr = p.find(q("w:pPr"))
    if ppr is not None and ppr.find(q("w:rPr")) is not None:
        return limpiar_rpr(ppr.find(q("w:rPr")))
    return None


def ppr_de(p):
    ppr = p.find(q("w:pPr"))
    return copy.deepcopy(ppr) if ppr is not None else None


def nuevo_run(texto: str, rpr=None):
    r = etree.Element(q("w:r"))
    if rpr is not None:
        r.append(copy.deepcopy(rpr))
    lineas = (texto or "").split("\n")
    for i, linea in enumerate(lineas):
        if i:
            etree.SubElement(r, q("w:br"))
        trozos = linea.split("\t")
        for j, trozo in enumerate(trozos):
            if j:
                etree.SubElement(r, q("w:tab"))
            if trozo:
                t = etree.SubElement(r, q("w:t"))
                t.text = trozo
                t.set(q("xml:space"), "preserve")
    return r


def nuevo_parrafo(texto: str, ppr=None, rpr=None):
    p = etree.Element(q("w:p"))
    if ppr is not None:
        p.append(copy.deepcopy(ppr))
    if texto:
        p.append(nuevo_run(texto, rpr))
    return p


def vaciar_parrafo(p) -> None:
    """Quita todo el contenido del párrafo excepto sus propiedades (pPr)."""
    for hijo in list(p):
        if hijo.tag != q("w:pPr"):
            p.remove(hijo)


def quitar_negrita(rpr):
    if rpr is None:
        return None
    rpr = copy.deepcopy(rpr)
    for nombre in ("w:b", "w:bCs"):
        for e in rpr.findall(q(nombre)):
            rpr.remove(e)
    return rpr


def fuentes_usadas(root) -> set[tuple[str, str]]:
    """Pares (tipo, valor) de fuentes y tamaños usados en runs y marcas de párrafo."""
    usados: set[tuple[str, str]] = set()
    for rf in root.iter(q("w:rFonts")):
        for atributo in ("ascii", "hAnsi"):
            v = rf.get(q(f"w:{atributo}"))
            if v:
                usados.add(("fuente", v))
    for sz in root.iter(q("w:sz")):
        v = sz.get(q("w:val"))
        if v:
            usados.add(("tamaño", f"{int(v) / 2:g} pt"))
    return usados
