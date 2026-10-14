"""Contrato del trabajador: lectura de la minuta, guardado y edición.

Cada cuenta queda vinculada a la cédula del contratista que aparece en la minuta:
- La lectura (texto extraído) se guarda en el servidor; el programa solo devuelve su id.
- Al guardar, la cédula escrita debe aparecer en el texto de esa minuta.
- Una cédula solo puede estar en una cuenta, y una cuenta solo registra contratos de su cédula.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile

from auth import Usuario, usuario_actual
from config import MAX_ARCHIVO
from db import get_db
from errores import ErrorApi, no_encontrado
from routers import comun
from schemas import ContratoEditar, ContratoGuardar
from servicios import cedulas, cuentas, limites
from servicios.extractor import TIPOS_MIME, extraer_texto
from servicios.minuta import analizar_minuta

router = APIRouter(tags=["contratos"])


def _respuesta(contrato: dict | None) -> dict:
    if not contrato:
        return {"contrato": None, "obligaciones": []}
    obligs = comun.obligaciones(contrato["id"])
    for o in obligs:
        o["titulo_corto"] = comun.titulo_corto(o["texto"])
    return {"contrato": contrato, "obligaciones": obligs}


def _validar_obligaciones(obligaciones) -> None:
    claves = [(o.numero, o.tipo) for o in obligaciones]
    if len(claves) != len(set(claves)):
        raise ErrorApi(400, "obligaciones_repetidas", "Hay obligaciones con el mismo número. Revisa la numeración.")
    if not any(o.tipo == "especifica" for o in obligaciones):
        raise ErrorApi(400, "sin_especificas", "Agrega al menos una obligación específica.")


@router.post("/contratos/minuta")
def leer_minuta(archivo: UploadFile = File(...), u: Usuario = Depends(usuario_actual)):
    """Extrae los datos de la minuta para que el usuario los revise. Todavía no guarda el contrato."""
    if not cuentas.sin_limite(u.id):
        limites.verificar(u.id, "minuta", 15)
    contenido = comun.leer_archivo(archivo, MAX_ARCHIVO)
    tipo, texto = extraer_texto(archivo.filename or "minuta", contenido)
    db = get_db()
    ruta = f"{u.id}/tmp/{uuid.uuid4().hex}.{tipo}"
    db.subir("minutas", ruta, contenido, TIPOS_MIME[tipo])
    r = analizar_minuta(texto, u.id)
    lectura = db.insertar("lecturas_minuta", {"user_id": u.id, "minuta_path": ruta, "texto": texto,
                                              "datos": r["datos"]})[0]
    avisos = list(r["avisos"])
    cedula = cedulas.normalizar((r["datos"].get("contratista") or {}).get("cedula"))
    if cedula:
        dueno = db.uno("profiles", {"cedula": cedula}, "id,email")
        if dueno and dueno["id"] != u.id:
            avisos.insert(0, f"La cédula de esta minuta ya está vinculada a otra cuenta "
                             f"({cedulas.ocultar_correo(dueno.get('email'))}). No podrás guardarla en esta cuenta.")
    return {"lectura_id": lectura["id"], "datos": r["datos"], "avisos": avisos, "modelo": r["modelo"]}


@router.post("/contratos")
def guardar_contrato(body: ContratoGuardar, u: Usuario = Depends(usuario_actual)):
    """Guarda el contrato revisado y sus obligaciones. Si había otro contrato activo, queda inactivo."""
    db = get_db()
    lectura = db.uno("lecturas_minuta", {"id": body.lectura_id, "user_id": u.id})
    if not lectura:
        raise ErrorApi(400, "lectura_invalida", "No encontramos la lectura de tu minuta. Vuelve a subirla.")
    _validar_obligaciones(body.obligaciones)

    cedula = cedulas.normalizar(body.contratista.cedula)
    if len(cedula) < 5:
        raise ErrorApi(400, "cedula_invalida", "Escribe tu número de cédula tal como aparece en la minuta.")
    if not cedulas.aparece_en_texto(cedula, lectura["texto"]):
        raise ErrorApi(400, "cedula_no_en_minuta",
                       "La cédula que escribiste no aparece en la minuta que subiste. Revisa el número: "
                       "debe ser la del contratista que firma el contrato.")
    cedulas.vincular(u.id, cedula)  # una cédula = una cuenta

    datos_json = dict(lectura.get("datos") or {})
    datos_json["contratista"] = {"nombre": body.contratista.nombre, "cedula": cedula}
    fila = {**body.contrato.model_dump(mode="json"), "user_id": u.id, "activo": True,
            "cedula_contratista": cedula, "texto_extraido": lectura["texto"], "datos_json": datos_json}

    db.actualizar("contratos", {"user_id": u.id, "activo": True}, {"activo": False})
    contrato = db.insertar("contratos", fila)[0]
    ruta = lectura["minuta_path"]
    destino = f"{u.id}/{contrato['id']}.{ruta.rsplit('.', 1)[-1]}"
    try:
        db.mover("minutas", ruta, destino)
        db.actualizar("contratos", {"id": contrato["id"]}, {"minuta_path": destino})
    except ErrorApi:
        db.actualizar("contratos", {"id": contrato["id"]}, {"minuta_path": ruta})
    db.insertar("obligaciones", [{"contrato_id": contrato["id"], "numero": o.numero, "tipo": o.tipo,
                                  "texto": o.texto, "palabras_clave": o.palabras_clave}
                                 for o in body.obligaciones])
    if body.contratista.nombre:
        db.actualizar("profiles", {"id": u.id}, {"nombre_completo": body.contratista.nombre})
    db.borrar("lecturas_minuta", {"id": lectura["id"]})
    return _respuesta(comun.contrato_activo(u.id))


@router.get("/contratos/actual")
def contrato_actual(u: Usuario = Depends(usuario_actual)):
    return _respuesta(comun.contrato_activo(u.id, requerido=False))


@router.put("/contratos/{contrato_id}")
def editar_contrato(contrato_id: str, body: ContratoEditar, u: Usuario = Depends(usuario_actual)):
    """Edita los datos del contrato y sincroniza sus obligaciones (editar, agregar, eliminar).

    La cédula no se puede cambiar: está vinculada a la cuenta.
    """
    db = get_db()
    actual = db.uno("contratos", {"id": contrato_id, "user_id": u.id})
    if not actual:
        raise no_encontrado("El contrato")
    _validar_obligaciones(body.obligaciones)
    vinculada = cedulas.normalizar(comun.perfil(u.id).get("cedula"))
    enviada = cedulas.normalizar(body.contratista.cedula)
    if enviada and vinculada and enviada != vinculada:
        raise ErrorApi(409, "cedula_distinta",
                       "La cédula está vinculada a tu cuenta y no se puede cambiar. Si hay un error, escríbenos.")

    datos_json = dict(actual.get("datos_json") or {})
    if body.contratista.nombre:
        datos_json["contratista"] = {"nombre": body.contratista.nombre, "cedula": vinculada or enviada}
    db.actualizar("contratos", {"id": contrato_id}, {**body.contrato.model_dump(mode="json"),
                                                      "datos_json": datos_json})

    existentes = {o["id"]: o for o in db.select("obligaciones", {"contrato_id": contrato_id})}
    enviados = {o.id for o in body.obligaciones if o.id}
    if enviados - set(existentes):
        raise ErrorApi(400, "obligacion_invalida", "Una de las obligaciones no pertenece a este contrato.")
    borrar = [i for i in existentes if i not in enviados]
    if borrar:
        db.borrar("obligaciones", {"id": borrar})
    cambian = [o for o in body.obligaciones if o.id and
               (existentes[o.id]["numero"], existentes[o.id]["tipo"]) != (o.numero, o.tipo)]
    # Paso intermedio para que un intercambio de números no choque con el índice único
    for o in cambian:
        db.actualizar("obligaciones", {"id": o.id}, {"numero": existentes[o.id]["numero"] + 1000})
    for o in body.obligaciones:
        valores = {"numero": o.numero, "tipo": o.tipo, "texto": o.texto, "palabras_clave": o.palabras_clave}
        if o.id:
            db.actualizar("obligaciones", {"id": o.id}, valores)
        else:
            db.insertar("obligaciones", {**valores, "contrato_id": contrato_id})
    if body.contratista.nombre:
        db.actualizar("profiles", {"id": u.id}, {"nombre_completo": body.contratista.nombre})
    return _respuesta(db.uno("contratos", {"id": contrato_id}, comun.COLUMNAS_CONTRATO))
