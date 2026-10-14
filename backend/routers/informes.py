"""Informe del periodo: vista agrupada por obligación, generación con control de cupo y descarga."""
from __future__ import annotations

import logging
import threading
from datetime import date

from fastapi import APIRouter, Depends, Query

from auth import Usuario, usuario_actual
from config import GENERACIONES_POR_HORA
from db import get_db
from errores import ErrorApi
from routers import comun
from schemas import GenerarEntrada
from servicios import alertas, capturas, conversor_pdf, cuentas, cupo, limites, periodos, verificacion
from servicios import evidencias as evidencias_srv
from servicios.extractor import TIPOS_MIME, nombre_seguro
from servicios.generador_docx import DatosInforme, ErrorPlantilla, ImagenAnexo, ObligacionInforme, generar

log = logging.getLogger("portal.informes")
router = APIRouter(tags=["informes"])

_CACHE_PLANTILLAS: dict[str, tuple[bytes, bytes | None]] = {}
_LOCK_CACHE = threading.Lock()


def _plantilla_y_pdf(plantilla: dict) -> tuple[bytes, bytes | None]:
    """Archivo de la plantilla y su PDF en blanco (para la verificación), en memoria."""
    with _LOCK_CACHE:
        if plantilla["id"] in _CACHE_PLANTILLAS:
            return _CACHE_PLANTILLAS[plantilla["id"]]
    contenido = get_db().descargar("plantillas", plantilla["archivo_path"])
    pdf = conversor_pdf.convertir(contenido)
    with _LOCK_CACHE:
        _CACHE_PLANTILLAS[plantilla["id"]] = (contenido, pdf)
    return contenido, pdf


def _agrupado(contrato: dict, informe: dict, user_id: str) -> dict:
    db = get_db()
    obligs = comun.obligaciones(contrato["id"], solo_especificas=True)
    acts = db.select("actividades", {"informe_id": informe["id"], "user_id": user_id},
                     orden="fecha.asc,created_at.asc")
    evidencias: dict[str, list] = {}
    if acts:
        for e in db.select("evidencias", {"actividad_id": [a["id"] for a in acts], "user_id": user_id},
                           "id,actividad_id,nombre,path,descripcion,created_at", orden="created_at.asc"):
            evidencias.setdefault(e["actividad_id"], []).append(e)
    for a in acts:
        a["evidencias"] = evidencias.get(a["id"], [])
    ids_especificas = {o["id"] for o in obligs}
    grupos = []
    for o in obligs:
        propias = [a for a in acts if a.get("obligacion_id") == o["id"]]
        grupos.append({**o, "titulo_corto": comun.titulo_corto(o["texto"]), "actividades": propias,
                       "confirmadas": sum(1 for a in propias if a["estado"] == "confirmada")})
    sin_obligacion = [a for a in acts if a.get("obligacion_id") not in ids_especificas]
    return {"obligaciones": grupos, "sin_obligacion": sin_obligacion, "actividades": acts}


@router.get("/informes/actual")
def informe_actual(periodo: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
                   u: Usuario = Depends(usuario_actual)):
    """Informe del periodo pedido (YYYY-MM) o del mes en curso, con actividades agrupadas y alertas."""
    contrato = comun.contrato_activo(u.id)
    fecha = periodos.desde_clave(periodo) if periodo else periodos.hoy()
    informe = comun.informe_para_fecha(contrato, u.id, fecha)
    datos = _agrupado(contrato, informe, u.id)
    ini, fin = periodos.a_fecha(informe["periodo_inicio"]), periodos.a_fecha(informe["periodo_fin"])
    lista_alertas = alertas.calcular(contrato, comun.perfil(u.id), ini, fin,
                                     [{"id": o["id"], "numero": o["numero"]} for o in datos["obligaciones"]],
                                     datos["actividades"])
    con_informe = [periodos.clave(periodos.a_fecha(i["periodo_inicio"]))
                   for i in get_db().select("informes", {"contrato_id": contrato["id"]}, "periodo_inicio")]
    total = len(datos["actividades"])
    return {
        "informe": informe,
        "periodo": {"clave": periodos.clave(ini), "etiqueta": periodos.etiqueta(ini.year, ini.month),
                    "inicio": ini.isoformat(), "fin": fin.isoformat()},
        "periodos": periodos.lista(contrato, con_informe),
        "obligaciones": datos["obligaciones"],
        "sin_obligacion": datos["sin_obligacion"],
        "alertas": lista_alertas,
        "conteo": {"total": total,
                   "confirmadas": sum(1 for a in datos["actividades"] if a["estado"] == "confirmada"),
                   "sin_obligacion": len(datos["sin_obligacion"])},
    }


def _minuscula_inicial(s: str) -> str:
    return s[:1].lower() + s[1:] if s else s


def texto_con_anexos(texto: str, refs: list[tuple[int, str]]) -> str:
    """Agrega a la actividad la referencia a sus anexos: 'Se adjunta como evidencia el Anexo 1: …'."""
    texto = texto.strip()
    if not refs:
        return texto
    if not texto.endswith((".", "!", "?")):
        texto += "."
    if len(refs) == 1:
        n, d = refs[0]
        return f"{texto} Se adjunta como evidencia el Anexo {n}: {_minuscula_inicial(d)}."
    partes = "; ".join(f"Anexo {n}: {_minuscula_inicial(d)}" for n, d in refs)
    return f"{texto} Se adjuntan como evidencia los anexos ({partes})."


def _datos_informe(contrato: dict, perfil: dict, informe: dict, grupos: list[dict], tipo: str,
                   fecha_elaboracion: date, descargar=None) -> DatosInforme:
    """descargar(ruta) -> bytes: trae la imagen de Storage para pegarla al final del informe."""
    obligaciones, anexos, imagenes, datos_avisos = [], [], [], []
    for g in grupos:
        textos = []
        for a in g["actividades"]:
            if a["estado"] != "confirmada":
                continue
            texto = (a.get("texto_redactado") or a["texto_original"]).strip()
            refs = []
            for e in a.get("evidencias") or []:
                nombre = e.get("nombre") or e["path"]
                desc = (e.get("descripcion") or "").strip().rstrip(".") or \
                    evidencias_srv.descripcion_respaldo(texto, evidencias_srv.tipo_de(nombre))
                numero = len(anexos) + 1
                imagen = evidencias_srv.es_imagen(nombre)
                pegado = False
                if descargar:
                    try:
                        contenido = descargar(e["path"])
                        if imagen:
                            imagenes.append(ImagenAnexo(numero, desc, contenido))
                            pegado = True
                        else:  # PDF, Word o Excel: se pegan capturas de sus páginas
                            tipo = nombre.lower().rsplit(".", 1)[-1]
                            paginas, total = capturas.paginas(contenido, tipo)
                            for i, jpeg in enumerate(paginas, 1):
                                imagenes.append(ImagenAnexo(numero, desc, jpeg, origen="documento",
                                                            etiqueta=f"página {i} de {total}" if total > 1 else ""))
                            pegado = bool(paginas)
                            if total > len(paginas):
                                datos_avisos.append(f"Anexo {numero}: el documento tiene {total} páginas; se pegaron "
                                                    f"las primeras {len(paginas)}.")
                            if not paginas:
                                datos_avisos.append(f"Anexo {numero}: no se pudo tomar captura de «{nombre}»; "
                                                    "queda como archivo adjunto.")
                    except Exception:
                        log.warning("No se pudo descargar la evidencia %s", e["id"])
                anexos.append(f"{desc} (obligación {g['numero']})."
                              + ("" if pegado else " Se entrega como archivo adjunto."))
                refs.append((numero, desc))
            textos.append(texto_con_anexos(texto, refs))
        obligaciones.append(ObligacionInforme(numero=g["numero"], texto=g["texto"], actividades=textos))
    f = periodos.a_fecha
    return DatosInforme(
        nombre_contratista=perfil.get("nombre_completo") or "", cedula=perfil.get("cedula") or "",
        numero_contrato=contrato.get("numero_contrato") or "", fecha_contrato=f(contrato.get("fecha_contrato")),
        objeto=contrato.get("objeto") or "", fecha_inicio=f(contrato.get("fecha_inicio")),
        fecha_fin=f(contrato.get("fecha_fin")), dependencia=contrato.get("dependencia") or "",
        supervisor_nombre=contrato.get("supervisor_nombre") or "",
        supervisor_cargo=contrato.get("supervisor_cargo") or "",
        periodo_inicio=f(informe["periodo_inicio"]), periodo_fin=f(informe["periodo_fin"]),
        fecha_elaboracion=fecha_elaboracion, tipo=tipo, obligaciones=obligaciones, anexos=anexos,
        imagenes=imagenes, avisos=datos_avisos)


@router.post("/informes/{informe_id}/generar")
def generar_informe(informe_id: str, body: GenerarEntrada, u: Usuario = Depends(usuario_actual)):
    """Descuenta el cupo, rellena la plantilla y entrega DOCX y PDF. Si algo falla, devuelve el cupo."""
    db = get_db()
    informe = comun.informe_propio(u.id, informe_id)
    if not cuentas.sin_limite(u.id):
        limites.verificar(u.id, "generar", GENERACIONES_POR_HORA)
    contrato = db.uno("contratos", {"id": informe["contrato_id"], "user_id": u.id}, comun.COLUMNAS_CONTRATO)
    datos = _agrupado(contrato, informe, u.id)
    if not any(a["estado"] == "confirmada" for g in datos["obligaciones"] for a in g["actividades"]):
        raise ErrorApi(400, "sin_actividades",
                       "Registra y confirma al menos una actividad en tus obligaciones antes de generar el informe.")
    plantilla = comun.plantilla_activa(u.id)
    if not plantilla or not plantilla.get("mapa_campos"):
        raise ErrorApi(409, "sin_plantilla", "No hay una plantilla de informe configurada.")

    resultado = cupo.consumir(u.id, informe_id)
    if not resultado.get("permitido"):
        limite = resultado.get("limite")
        if resultado.get("motivo") == "sin_cedula":
            raise ErrorApi(409, "sin_cedula", "Tu cuenta no tiene una cédula vinculada. Vuelve a cargar tu minuta "
                                              "en Perfil > Cargar un contrato nuevo.")
        detalle = (" La prueba gratis es una sola por persona (cédula)." if resultado.get("plan") == "gratis" else "")
        raise ErrorApi(402, "limite_alcanzado",
                       f"Ya usaste los {limite} informes de tu plan.{detalle} Elige un plan para seguir generando "
                       "informes.", plan=resultado.get("plan"), usados=resultado.get("usados"), limite=limite)
    try:
        plantilla_docx, plantilla_pdf = _plantilla_y_pdf(plantilla)
        di = _datos_informe(contrato, comun.perfil(u.id), informe, datos["obligaciones"], body.tipo,
                            body.fecha_elaboracion or periodos.hoy(),
                            descargar=lambda ruta: db.descargar("evidencias", ruta))
        docx = generar(plantilla_docx, plantilla["mapa_campos"], di)
        pdf = conversor_pdf.convertir(docx)
        advertencias = di.avisos + verificacion.verificar(plantilla_docx, docx, plantilla_pdf, pdf)
        if pdf is None:
            advertencias.append("No se pudo crear el PDF en el servidor; descarga el Word.")
        ruta_docx = f"{u.id}/{informe_id}.docx"
        db.subir("informes", ruta_docx, docx, TIPOS_MIME["docx"])
        ruta_pdf = None
        if pdf:
            ruta_pdf = f"{u.id}/{informe_id}.pdf"
            db.subir("informes", ruta_pdf, pdf, TIPOS_MIME["pdf"])
        informe = db.actualizar("informes", {"id": informe_id, "user_id": u.id},
                                {"docx_path": ruta_docx, "pdf_path": ruta_pdf, "estado": "finalizado",
                                 "tipo": body.tipo, "plantilla_id": plantilla["id"]})[0]
    except Exception as exc:
        if resultado.get("cobrado"):
            try:
                cupo.devolver(u.id, informe_id, resultado["ciclo"])
            except Exception:
                log.exception("No se pudo devolver el cupo del informe %s", informe_id)
        log.exception("Falló la generación del informe %s", informe_id)
        if isinstance(exc, ErrorPlantilla):
            raise ErrorApi(500, "plantilla_invalida", f"La plantilla tiene un problema: {exc} No se descontó tu cupo.")
        raise ErrorApi(500, "generacion_fallida",
                       "No pudimos generar el informe. No se descontó de tu cupo; intenta de nuevo.")
    return {"informe": informe, "pdf": ruta_pdf is not None, "advertencias": advertencias,
            "cobrado": bool(resultado.get("cobrado")), "sin_limite": bool(resultado.get("sin_limite")),
            "suscripcion": cupo.estado(u.id)}


@router.get("/informes/{informe_id}/descargar")
def descargar_informe(informe_id: str, formato: str = Query(pattern="^(docx|pdf)$"),
                      u: Usuario = Depends(usuario_actual)):
    """URL firmada temporal (5 minutos) para descargar el informe generado."""
    informe = comun.informe_propio(u.id, informe_id)
    ruta = informe.get(f"{formato}_path")
    if not ruta:
        raise ErrorApi(404, "sin_archivo", "Ese informe todavía no se ha generado en ese formato.")
    contrato = get_db().uno("contratos", {"id": informe["contrato_id"]}, "numero_contrato")
    ini = periodos.a_fecha(informe["periodo_inicio"])
    nombre = nombre_seguro(f"Informe_{(contrato or {}).get('numero_contrato') or 'contrato'}_"
                           f"{periodos.MESES[ini.month - 1]}_{ini.year}.{formato}")
    return {"url": get_db().url_firmada("informes", ruta, 300, descarga=nombre), "nombre": nombre,
            "expira_en": 300}
