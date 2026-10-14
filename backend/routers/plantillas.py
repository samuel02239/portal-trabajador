"""Plantilla del informe: la oficial (global) o una propia que sube el usuario."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile

from auth import Usuario, usuario_actual
from config import MAX_ARCHIVO
from db import get_db
from errores import ErrorApi, no_encontrado
from routers import comun
from schemas import ConfirmarPlantilla
from servicios import mapa_plantilla
from servicios.extractor import TIPOS_MIME, nombre_seguro, validar_archivo

router = APIRouter(tags=["plantillas"])


def _publica(p: dict | None) -> dict | None:
    if not p:
        return None
    return {k: p.get(k) for k in ("id", "alcance", "nombre", "formato", "activa", "created_at")}


@router.get("/plantillas/actual")
def plantilla_actual(u: Usuario = Depends(usuario_actual)):
    p = comun.plantilla_activa(u.id)
    return {"plantilla": _publica(p),
            "resumen": mapa_plantilla.resumen(p["mapa_campos"]) if p and p.get("mapa_campos") else []}


@router.post("/plantillas")
def subir_plantilla(archivo: UploadFile = File(...), alcance: str = Form("usuario"),
                    u: Usuario = Depends(usuario_actual)):
    """Sube una plantilla en blanco y propone su mapa de campos. Queda inactiva hasta que se confirme."""
    db = get_db()
    if alcance not in ("usuario", "global"):
        raise ErrorApi(400, "alcance_invalido", "El alcance debe ser 'usuario' o 'global'.")
    if alcance == "global" and comun.perfil(u.id).get("rol") != "admin":
        raise ErrorApi(403, "prohibido", "Solo un administrador puede publicar plantillas globales.")
    contenido = comun.leer_archivo(archivo, MAX_ARCHIVO)
    tipo = validar_archivo(archivo.filename or "plantilla.docx", contenido, {"docx", "pdf"})
    if tipo == "pdf":
        raise ErrorApi(415, "plantilla_pdf",
                       "La plantilla debe estar en Word (.docx) para conservar su formato exacto. "
                       "Pide la versión Word al área responsable.")
    mapa = mapa_plantilla.detectar(contenido)
    mapa, modelo = mapa_plantilla.completar_con_ia(contenido, mapa, u.id)
    plantilla_id = str(uuid.uuid4())
    carpeta = "global" if alcance == "global" else u.id
    ruta = f"{carpeta}/{plantilla_id}.docx"
    db.subir("plantillas", ruta, contenido, TIPOS_MIME["docx"])
    fila = db.insertar("plantillas_informe", {
        "id": plantilla_id, "alcance": alcance, "user_id": None if alcance == "global" else u.id,
        "nombre": nombre_seguro(archivo.filename or "plantilla.docx"), "formato": "docx",
        "archivo_path": ruta, "mapa_campos": mapa, "activa": False})[0]
    return {"plantilla": _publica(fila), "mapa_campos": mapa, "resumen": mapa_plantilla.resumen(mapa),
            "faltantes": mapa_plantilla.faltantes(mapa), "modelo": modelo}


@router.post("/plantillas/{plantilla_id}/confirmar")
def confirmar_plantilla(plantilla_id: str, body: ConfirmarPlantilla, u: Usuario = Depends(usuario_actual)):
    """El usuario confirma el mapa una sola vez; la plantilla queda activa."""
    db = get_db()
    p = db.uno("plantillas_informe", {"id": plantilla_id})
    es_admin = comun.perfil(u.id).get("rol") == "admin"
    if not p or (p["alcance"] == "usuario" and p["user_id"] != u.id) or (p["alcance"] == "global" and not es_admin):
        raise no_encontrado("La plantilla")
    mapa = body.mapa_campos or p["mapa_campos"]
    if "ejecucion" in mapa_plantilla.faltantes(mapa):
        raise ErrorApi(400, "mapa_incompleto", "No se encontró la tabla de obligaciones y actividades en la plantilla.")
    if p["alcance"] == "usuario":
        db.actualizar("plantillas_informe", {"user_id": u.id, "alcance": "usuario", "activa": True}, {"activa": False})
    else:
        db.actualizar("plantillas_informe", {"alcance": "global", "activa": True}, {"activa": False})
    fila = db.actualizar("plantillas_informe", {"id": plantilla_id}, {"mapa_campos": mapa, "activa": True})[0]
    return {"plantilla": _publica(fila), "resumen": mapa_plantilla.resumen(mapa)}


@router.delete("/plantillas/{plantilla_id}")
def dejar_de_usar(plantilla_id: str, u: Usuario = Depends(usuario_actual)):
    """Desactiva una plantilla propia; el usuario vuelve a la plantilla oficial."""
    db = get_db()
    p = db.uno("plantillas_informe", {"id": plantilla_id, "user_id": u.id, "alcance": "usuario"})
    if not p:
        raise no_encontrado("La plantilla")
    db.actualizar("plantillas_informe", {"id": plantilla_id}, {"activa": False})
    return {"plantilla": _publica(comun.plantilla_activa(u.id))}
