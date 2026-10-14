"""Rellena la plantilla oficial en su lugar (sección 8.2), sin reconstruir el documento.

- En cada celda se reutiliza el formato del run existente (rPr: fuente, tamaño,
  negrita, color) o el de la marca de párrafo si la celda está vacía.
- Si hay más obligaciones que filas, se clona la última fila (copy.deepcopy del
  XML) para conservar bordes y formato. Las filas sobrantes se eliminan.
- Las actividades de cada obligación van como viñetas, ordenadas por fecha, con
  el mismo párrafo de viñeta que trae la plantilla en su fila de ejemplo.
- Se marca "Informe parcial" o "Informe final" escribiendo una X en su casilla.
- Las firmas no se tocan.
"""
from __future__ import annotations

import copy
import io
import re
from dataclasses import dataclass, field
from datetime import date

from docx import Document
from lxml import etree

from servicios.docx_util import (NS, celdas, filas, nuevo_parrafo, nuevo_run, parrafos_cuerpo, parrafos_de, ppr_de, q,
                                 quitar_negrita, rpr_de_parrafo, tablas_cuerpo, texto_de, vaciar_parrafo)
from servicios.periodos import MESES, fecha_larga

_BLANCO = re.compile(r"_{2,}")


class ErrorPlantilla(Exception):
    pass


@dataclass
class ObligacionInforme:
    numero: int
    texto: str
    actividades: list[str] = field(default_factory=list)


@dataclass
class ImagenAnexo:
    numero: int
    descripcion: str
    contenido: bytes


@dataclass
class DatosInforme:
    nombre_contratista: str = ""
    cedula: str = ""
    numero_contrato: str = ""
    fecha_contrato: date | None = None
    objeto: str = ""
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    dependencia: str = ""
    supervisor_nombre: str = ""
    supervisor_cargo: str = ""
    periodo_inicio: date | None = None
    periodo_fin: date | None = None
    fecha_elaboracion: date | None = None
    tipo: str = "parcial"
    obligaciones: list[ObligacionInforme] = field(default_factory=list)
    anexos: list[str] = field(default_factory=list)
    imagenes: list[ImagenAnexo] = field(default_factory=list)

    def valor_campo(self, campo: str) -> str:
        f = lambda d: fecha_larga(d) if d else ""  # noqa: E731
        supervisor = " - ".join(x for x in (self.supervisor_nombre, self.supervisor_cargo) if x)
        return {
            "nombre_contratista": self.nombre_contratista, "cedula": self.cedula,
            "numero_contrato": self.numero_contrato, "fecha_contrato": f(self.fecha_contrato),
            "objeto": self.objeto, "fecha_inicio": f(self.fecha_inicio), "fecha_fin": f(self.fecha_fin),
            "dependencia": self.dependencia, "supervisor": supervisor,
        }.get(campo, "") or ""


# ------------------------------------------------------------------ operaciones
def escribir_celda(tc, texto: str) -> None:
    """Escribe en una celda de valor conservando el formato que trae la plantilla."""
    ps = parrafos_de(tc)
    if not ps:
        tc.append(etree.Element(q("w:p")))
        ps = parrafos_de(tc)
    rpr = None
    for p in ps:
        rpr = rpr_de_parrafo(p)
        if rpr is not None:
            break
    primero = ps[0]
    vaciar_parrafo(primero)
    primero.append(nuevo_run(texto, rpr))
    # Los renglones vacíos que la plantilla usaba para dar altura sobran con el texto escrito
    for p in ps[1:]:
        if not texto_de(p).replace("\xa0", " ").strip():
            tc.remove(p)


def llenar_blancos(p, valores: list[str | None]) -> int:
    """Reemplaza, en orden, cada secuencia de guiones bajos (___) del párrafo por un valor.

    Funciona aunque los guiones estén repartidos en varios runs. Devuelve cuántos reemplazó.
    """
    segmentos = []  # [elemento w:t, inicio, fin] dentro del texto completo
    total = ""
    for t in p.iter(q("w:t")):
        if any(a.tag == q("w:txbxContent") for a in t.iterancestors()):
            continue
        inicio = len(total)
        total += t.text or ""
        segmentos.append((t, inicio, len(total)))
    coincidencias = list(_BLANCO.finditer(total))
    n = min(len(coincidencias), len(valores))
    for i in reversed(range(n)):  # de atrás hacia adelante: los índices previos siguen válidos
        valor = valores[i]
        if valor is None:
            continue
        m = coincidencias[i]
        primero = True
        for t, s, e in segmentos:
            a, b = max(s, m.start()), min(e, m.end())
            if a >= b:
                continue
            texto = t.text or ""
            t.text = texto[:a - s] + (valor if primero else "") + texto[b - s:]
            t.set(q("xml:space"), "preserve")
            primero = False
    return n


def marcar_casilla(parrafos: list, indice: int) -> bool:
    """Escribe una X en el cuadro de texto vacío número 'indice' (de izquierda a derecha)."""
    cajas = []
    for p in parrafos:
        for ac in p.iter(q("mc:AlternateContent")):
            caja = ac.find(f".//{q('wps:txbx')}")
            if caja is None or texto_de(caja.find(q("w:txbxContent"))).strip():
                continue
            pos = ac.find(f".//{q('wp:positionH')}/{q('wp:posOffset')}")
            x = int(pos.text) if pos is not None and (pos.text or "").lstrip("-").isdigit() else 0
            contenidos = list(ac.iter(q("w:txbxContent")))  # versión moderna (wps) y de respaldo (VML)
            cajas.append((x, contenidos))
    if indice >= len(cajas):
        return False
    cajas.sort(key=lambda c: c[0])
    rpr = etree.fromstring(
        f'<w:rPr xmlns:w="{NS["w"]}"><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
        '<w:b/><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr>')
    for contenido in cajas[indice][1]:
        p = contenido.find(q("w:p"))
        if p is None:
            p = etree.SubElement(contenido, q("w:p"))
        vaciar_parrafo(p)
        ppr = p.find(q("w:pPr"))
        if ppr is None:
            ppr = etree.Element(q("w:pPr"))
            p.insert(0, ppr)
        for hijo in list(ppr):
            if hijo.tag in (q("w:spacing"), q("w:jc")):
                ppr.remove(hijo)
        spacing = etree.SubElement(ppr, q("w:spacing"))
        spacing.set(q("w:before"), "0")
        spacing.set(q("w:after"), "0")
        spacing.set(q("w:line"), "240")
        spacing.set(q("w:lineRule"), "auto")
        jc = etree.SubElement(ppr, q("w:jc"))
        jc.set(q("w:val"), "center")
        p.append(nuevo_run("X", rpr))
    return True


@dataclass
class _Formato:
    ppr: object = None
    rpr: object = None


def _formato_de_celda(tc, preferir_vineta: bool = False) -> _Formato:
    ps = parrafos_de(tc)
    if not ps:
        return _Formato()
    elegido = None
    if preferir_vineta:
        elegido = next((p for p in ps if p.find(f"{q('w:pPr')}/{q('w:numPr')}") is not None), None)
    if elegido is None:
        elegido = next((p for p in ps if texto_de(p).strip()), ps[0])
    return _Formato(ppr_de(elegido), rpr_de_parrafo(elegido))


def _poner_parrafos(tc, nuevos: list) -> None:
    for p in parrafos_de(tc):
        tc.remove(p)
    for p in nuevos:
        tc.append(p)


def llenar_ejecucion(tbl, conf: dict, obligaciones: list[ObligacionInforme]) -> None:
    todas = filas(tbl)
    inicio = conf["fila_inicio"]
    datos = todas[inicio:]
    if not datos:
        raise ErrorPlantilla("La tabla de ejecución no tiene filas para llenar.")
    ci, co, ca = conf.get("col_item"), conf["col_obligacion"], conf["col_actividades"]

    fila_fmt = todas[conf["fila_formato"]] if conf.get("fila_formato") is not None else datos[0]
    tcs_fmt = celdas(fila_fmt)
    fmt_item = _formato_de_celda(tcs_fmt[ci]) if ci is not None and ci < len(tcs_fmt) else _Formato()
    fmt_obl = _formato_de_celda(tcs_fmt[co])
    fmt_vineta = _formato_de_celda(tcs_fmt[ca], preferir_vineta=True)
    hay_vineta = fmt_vineta.ppr is not None and fmt_vineta.ppr.find(q("w:numPr")) is not None
    fmt_act = _formato_de_celda(tcs_fmt[ca])
    if fmt_act.ppr is not None and fmt_act.ppr.find(q("w:numPr")) is not None:
        fmt_act = fmt_obl  # párrafo normal (sin viñeta) para celdas sin actividades

    modelo = copy.deepcopy(datos[-1])  # la última fila suele ser una fila vacía "limpia"
    while len(datos) < len(obligaciones):
        nueva = copy.deepcopy(modelo)
        datos[-1].addnext(nueva)
        datos.append(nueva)
    if conf.get("eliminar_sobrantes", True) and obligaciones:
        for tr in datos[len(obligaciones):]:
            tbl.remove(tr)
        datos = datos[:len(obligaciones)]

    for tr, ob in zip(datos, obligaciones):
        tcs = celdas(tr)
        if ci is not None and ci < len(tcs):
            _poner_parrafos(tcs[ci], [nuevo_parrafo(str(ob.numero), fmt_item.ppr, fmt_item.rpr)])
        _poner_parrafos(tcs[co], [nuevo_parrafo(ob.texto, fmt_obl.ppr, fmt_obl.rpr)])
        if ob.actividades:
            if hay_vineta:
                parrafos = [nuevo_parrafo(t, fmt_vineta.ppr, fmt_vineta.rpr) for t in ob.actividades]
            else:
                parrafos = [nuevo_parrafo(f"• {t}", fmt_act.ppr, fmt_act.rpr) for t in ob.actividades]
        else:
            parrafos = [nuevo_parrafo("", fmt_act.ppr, fmt_act.rpr)]
        _poner_parrafos(tcs[ca], parrafos)


def llenar_anexos(parrafos: list, conf: dict, anexos: list[str]) -> None:
    items = [parrafos[i] for i in conf.get("items", []) if i < len(parrafos)]
    if not items or not anexos:
        return
    molde = copy.deepcopy(items[-1])
    while len(items) < len(anexos):
        nuevo = copy.deepcopy(molde)
        for t in nuevo.iter(q("w:t")):
            if re.fullmatch(r"\s*\d+\.\s*", t.text or ""):
                t.text = f"{len(items) + 1}."
                break
        items[-1].addnext(nuevo)
        items.append(nuevo)
    for p, texto in zip(items, anexos):
        rpr = quitar_negrita(rpr_de_parrafo(p))
        p.append(nuevo_run(f" {texto}", rpr))


def _rpr_arial():
    return etree.fromstring(f'<w:rPr xmlns:w="{NS["w"]}"><w:rFonts w:ascii="Arial" w:eastAsia="Arial" '
                            'w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>')


def _con_negrita(rpr):
    rpr = copy.deepcopy(rpr)
    if rpr.find(q("w:b")) is None:
        fuentes = rpr.find(q("w:rFonts"))
        posicion = list(rpr).index(fuentes) + 1 if fuentes is not None else 0
        rpr.insert(posicion, etree.Element(q("w:b")))
    return rpr


def _escribir(parrafo, texto: str, rpr) -> None:
    run = parrafo.add_run(texto)
    existente = run._r.find(q("w:rPr"))
    if existente is not None:
        run._r.remove(existente)
    run._r.insert(0, copy.deepcopy(rpr))


def pegar_imagenes(doc, imagenes: list[ImagenAnexo], rpr_base=None) -> int:
    """Pega las fotos de los anexos al final del documento (después del último cuadro), cada una con su título.

    Devuelve cuántas imágenes se pegaron.
    """
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.shared import Cm, Emu, Pt

    from servicios import imagenes as procesar

    preparadas = []
    for im in imagenes:
        lista = procesar.preparar(im.contenido)
        if lista:
            preparadas.append((im, *lista))
    if not preparadas:
        return 0
    seccion = doc.sections[-1]
    ancho_max = min(seccion.page_width - seccion.left_margin - seccion.right_margin, Cm(15))
    alto_max = Cm(8.6)  # caben dos fotos con su título por página
    base = rpr_base if rpr_base is not None else _rpr_arial()
    negrita, normal = _con_negrita(base), quitar_negrita(base)

    salto = doc.add_paragraph()
    salto.add_run().add_break(WD_BREAK.PAGE)
    titulo = doc.add_paragraph()
    titulo.paragraph_format.space_after = Pt(6)
    _escribir(titulo, "REGISTRO FOTOGRÁFICO DE LOS ANEXOS", negrita)
    for im, jpeg, ancho_px, alto_px in preparadas:
        escala = min(ancho_max / ancho_px, alto_max / alto_px)
        leyenda = doc.add_paragraph()
        leyenda.paragraph_format.keep_with_next = True
        leyenda.paragraph_format.space_before = Pt(10)
        leyenda.paragraph_format.space_after = Pt(4)
        _escribir(leyenda, f"Anexo {im.numero}. ", negrita)
        _escribir(leyenda, f"{im.descripcion.rstrip('.')}.", normal)
        foto = doc.add_paragraph()
        foto.alignment = WD_ALIGN_PARAGRAPH.CENTER
        foto.add_run().add_picture(io.BytesIO(jpeg), width=Emu(int(ancho_px * escala)),
                                   height=Emu(int(alto_px * escala)))
    return len(preparadas)


# --------------------------------------------------------------------- principal
def generar(plantilla: bytes, mapa: dict, datos: DatosInforme) -> bytes:
    doc = Document(io.BytesIO(plantilla))
    body = doc.element.body
    tablas = tablas_cuerpo(body)
    parrafos = parrafos_cuerpo(body)  # se resuelven todas las referencias antes de modificar

    def celda(ref: dict):
        try:
            return celdas(filas(tablas[ref["tabla"]])[ref["fila"]])[ref["col"]]
        except (IndexError, KeyError, TypeError):
            return None

    # 1. Información del contrato
    for campo, ref in (mapa.get("campos") or {}).items():
        valor = datos.valor_campo(campo)
        tc = celda(ref) if ref else None
        if tc is not None and valor:
            escribir_celda(tc, valor)

    parr = mapa.get("parrafos") or {}
    # 2. Fecha de elaboración
    ref = parr.get("fecha_elaboracion")
    if ref and datos.fecha_elaboracion and ref["indice"] < len(parrafos):
        llenar_blancos(parrafos[ref["indice"]], [fecha_larga(datos.fecha_elaboracion)])

    # 3. Informe parcial / final
    cas = mapa.get("casillas")
    if cas:
        zona = parrafos[cas["desde"]:cas["hasta"] + 1]
        marcar_casilla(zona, cas["final"] if datos.tipo == "final" else cas["parcial"])

    # 4. Periodo del informe
    ref = parr.get("periodo")
    if ref and datos.periodo_inicio and datos.periodo_fin and ref["indice"] < len(parrafos):
        i, f = datos.periodo_inicio, datos.periodo_fin
        llenar_blancos(parrafos[ref["indice"]],
                       [str(i.day), MESES[i.month - 1], str(f.day), MESES[f.month - 1], str(f.year)])

    # 5. Ejecución
    conf = mapa.get("ejecucion")
    if not conf:
        raise ErrorPlantilla("La plantilla no tiene identificada la tabla de ejecución.")
    if datos.obligaciones:
        llenar_ejecucion(tablas[conf["tabla"]], conf, datos.obligaciones)

    # 6. Anexos: lista con su descripción y, al final del documento, las fotos
    rpr_anexo = None
    conf_anexos = mapa.get("anexos") or {}
    if conf_anexos.get("items") and conf_anexos["items"][0] < len(parrafos):
        rpr_anexo = rpr_de_parrafo(parrafos[conf_anexos["items"][0]])
    if conf_anexos and datos.anexos:
        llenar_anexos(parrafos, conf_anexos, datos.anexos)
    if datos.imagenes:
        pegar_imagenes(doc, datos.imagenes, rpr_anexo)

    salida = io.BytesIO()
    doc.save(salida)
    return salida.getvalue()
