"""Actividades diarias: clasificación con IA, guardado, edición y evidencias."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile

from auth import Usuario, usuario_actual
from config import CLASIFICACIONES_POR_HORA, EVIDENCIAS_POR_HORA, MAX_ARCHIVO
from db import get_db
from errores import ErrorApi, no_encontrado
from ia import IAError, IANoConfigurada
from routers import comun
from schemas import ActividadCrear, ActividadEditar, ClasificarEntrada, EvidenciaEditar
from servicios import cuentas, evidencias, limites, periodos
from servicios.clasificador import clasificar
from servicios.extractor import TIPOS_MIME, nombre_seguro, validar_archivo

router = APIRouter(tags=["actividades"])

MENSAJE_IA = "No pudimos analizar esto ahora; guarda tu actividad y reintenta."


@router.post("/actividades/clasificar")
def clasificar_actividad(body: ClasificarEntrada, u: Usuario = Depends(usuario_actual)):
    """Propone obligación(es), confianza y redacción formal. No guarda nada."""
    contrato = comun.contrato_activo(u.id)
    obligs = comun.obligaciones(contrato["id"], solo_especificas=True)
    if not obligs:
        raise ErrorApi(409, "sin_obligaciones", "Tu contrato no tiene obligaciones específicas registradas.")
    if not cuentas.sin_limite(u.id):
        limites.verificar(u.id, "clasificar", CLASIFICACIONES_POR_HORA)
    fecha = body.fecha or periodos.hoy()
    try:
        return clasificar(body.texto.strip(), fecha.isoformat(), contrato, obligs, u.id)
    except IANoConfigurada as exc:
        raise ErrorApi(503, "ia_no_disponible", MENSAJE_IA, detalle=str(exc))
    except IAError:
        raise ErrorApi(503, "ia_no_disponible", MENSAJE_IA)


def _con_evidencias(actividad: dict) -> dict:
    actividad["evidencias"] = get_db().select("evidencias", {"actividad_id": actividad["id"]},
                                              "id,nombre,path,descripcion,created_at", orden="created_at.asc")
    return actividad


@router.post("/actividades")
def crear_actividad(body: ActividadCrear, u: Usuario = Depends(usuario_actual)):
    contrato = comun.contrato_activo(u.id)
    informe = comun.informe_para_fecha(contrato, u.id, body.fecha)
    if body.obligacion_id:
        comun.validar_obligacion(contrato["id"], body.obligacion_id)
        estado = "propuesta" if body.estado == "propuesta" else "confirmada"
    else:
        estado = "sin_obligacion" if body.estado == "sin_obligacion" else "propuesta"
    fila = {
        "informe_id": informe["id"], "user_id": u.id, "fecha": body.fecha.isoformat(),
        "texto_original": body.texto_original.strip(),
        "texto_redactado": (body.texto_redactado or "").strip() or None,
        "obligacion_id": body.obligacion_id, "confianza": body.confianza, "estado": estado,
        "modelo_usado": body.modelo_usado,
    }
    actividad = get_db().insertar("actividades", fila)[0]
    actividad["evidencias"] = []
    return actividad


@router.patch("/actividades/{actividad_id}")
def editar_actividad(actividad_id: str, body: ActividadEditar, u: Usuario = Depends(usuario_actual)):
    """Cambia la redacción, la fecha o la obligación. obligacion_id = null la deja 'sin_obligacion'."""
    actividad = comun.actividad_propia(u.id, actividad_id)
    enviados = body.model_fields_set
    cambios: dict = {}
    if "texto_redactado" in enviados and body.texto_redactado is not None:
        cambios["texto_redactado"] = body.texto_redactado.strip() or None
    contrato = None
    if "obligacion_id" in enviados:
        if body.obligacion_id:
            informe = comun.informe_propio(u.id, actividad["informe_id"])
            comun.validar_obligacion(informe["contrato_id"], body.obligacion_id)
            cambios.update(obligacion_id=body.obligacion_id, estado="confirmada")
        else:
            cambios.update(obligacion_id=None, estado="sin_obligacion")
    if "fecha" in enviados and body.fecha:
        cambios["fecha"] = body.fecha.isoformat()
        informe = comun.informe_propio(u.id, actividad["informe_id"])
        if not (periodos.a_fecha(informe["periodo_inicio"]) <= body.fecha <= periodos.a_fecha(informe["periodo_fin"])):
            contrato = get_db().uno("contratos", {"id": informe["contrato_id"], "user_id": u.id})
            cambios["informe_id"] = comun.informe_para_fecha(contrato, u.id, body.fecha)["id"]
    if not cambios:
        return _con_evidencias(actividad)
    return _con_evidencias(get_db().actualizar("actividades", {"id": actividad_id, "user_id": u.id}, cambios)[0])


@router.delete("/actividades/{actividad_id}")
def borrar_actividad(actividad_id: str, u: Usuario = Depends(usuario_actual)):
    comun.actividad_propia(u.id, actividad_id)
    db = get_db()
    rutas = [e["path"] for e in db.select("evidencias", {"actividad_id": actividad_id, "user_id": u.id}, "path")]
    if rutas:
        db.borrar_archivos("evidencias", rutas)
    db.borrar("actividades", {"id": actividad_id, "user_id": u.id})
    return {"ok": True}


def _describir_para(actividad: dict, nombre: str, user_id: str) -> str:
    """Descripción del anexo según la redacción de la actividad y su obligación."""
    obligacion = ""
    if actividad.get("obligacion_id"):
        o = get_db().uno("obligaciones", {"id": actividad["obligacion_id"]}, "texto")
        obligacion = (o or {}).get("texto") or ""
    texto = actividad.get("texto_redactado") or actividad["texto_original"]
    return evidencias.describir(texto, obligacion, nombre, user_id)


@router.post("/actividades/{actividad_id}/evidencias")
def subir_evidencia(actividad_id: str, archivo: UploadFile = File(...), u: Usuario = Depends(usuario_actual)):
    actividad = comun.actividad_propia(u.id, actividad_id)
    if not cuentas.sin_limite(u.id):
        limites.verificar(u.id, "evidencia", EVIDENCIAS_POR_HORA)
    contenido = comun.leer_archivo(archivo, MAX_ARCHIVO)
    tipo = validar_archivo(archivo.filename or "evidencia", contenido, {"pdf", "docx", "png", "jpg", "xlsx"})
    nombre = nombre_seguro(archivo.filename or f"evidencia.{tipo}")
    ruta = f"{u.id}/{actividad_id}/{uuid.uuid4().hex[:8]}_{nombre}"
    db = get_db()
    db.subir("evidencias", ruta, contenido, TIPOS_MIME[tipo])
    visible = (archivo.filename or nombre).replace("\\", "/").split("/")[-1][:150]
    return db.insertar("evidencias", {"actividad_id": actividad_id, "user_id": u.id, "path": ruta,
                                      "nombre": visible,
                                      "descripcion": _describir_para(actividad, nombre, u.id)})[0]


@router.patch("/actividades/{actividad_id}/evidencias/{evidencia_id}")
def editar_evidencia(actividad_id: str, evidencia_id: str, body: EvidenciaEditar,
                     u: Usuario = Depends(usuario_actual)):
    """Cambia el texto del anexo o lo vuelve a escribir con IA."""
    db = get_db()
    ev = db.uno("evidencias", {"id": evidencia_id, "actividad_id": actividad_id, "user_id": u.id})
    if not ev:
        raise no_encontrado("La evidencia")
    if body.regenerar:
        if not cuentas.sin_limite(u.id):
            limites.verificar(u.id, "evidencia", EVIDENCIAS_POR_HORA)
        descripcion = _describir_para(comun.actividad_propia(u.id, actividad_id), ev["nombre"] or ev["path"], u.id)
    else:
        descripcion = (body.descripcion or "").strip().rstrip(".")
        if len(descripcion) < 5:
            raise ErrorApi(400, "descripcion_corta", "Escribe una descripción del anexo de al menos unas palabras.")
    return db.actualizar("evidencias", {"id": evidencia_id, "user_id": u.id}, {"descripcion": descripcion})[0]


@router.delete("/actividades/{actividad_id}/evidencias/{evidencia_id}")
def borrar_evidencia(actividad_id: str, evidencia_id: str, u: Usuario = Depends(usuario_actual)):
    db = get_db()
    ev = db.uno("evidencias", {"id": evidencia_id, "actividad_id": actividad_id, "user_id": u.id})
    if not ev:
        raise no_encontrado("La evidencia")
    db.borrar_archivos("evidencias", [ev["path"]])
    db.borrar("evidencias", {"id": evidencia_id, "user_id": u.id})
    return {"ok": True}
