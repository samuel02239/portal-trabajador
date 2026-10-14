"""Consultas compartidas entre routers. Todas filtran por el user_id del token."""
from __future__ import annotations

import calendar
from datetime import date

from db import Op, get_db
from errores import ErrorApi, no_encontrado
from servicios import periodos

COLUMNAS_CONTRATO = ("id,user_id,numero_contrato,entidad,tipo_contratacion,proyecto,objeto,dependencia,"
                     "supervisor_nombre,supervisor_cargo,fecha_contrato,fecha_inicio,fecha_fin,plazo_texto,"
                     "valor_total,forma_pago,minuta_path,datos_json,activo,created_at")


def leer_archivo(archivo, maximo: int) -> bytes:
    """Lee un UploadFile sin pasar del máximo (lee un byte de más para detectar el exceso)."""
    return archivo.file.read(maximo + 1)


def perfil(user_id: str) -> dict:
    return get_db().uno("profiles", {"id": user_id}) or {}


def contrato_activo(user_id: str, requerido: bool = True) -> dict | None:
    c = get_db().uno("contratos", {"user_id": user_id, "activo": True}, COLUMNAS_CONTRATO)
    if not c and requerido:
        raise ErrorApi(409, "sin_contrato", "Primero sube tu minuta para registrar el contrato.")
    return c


def obligaciones(contrato_id: str, solo_especificas: bool = False) -> list[dict]:
    filtros = {"contrato_id": contrato_id}
    if solo_especificas:
        filtros["tipo"] = "especifica"
    filas = get_db().select("obligaciones", filtros, "id,numero,tipo,texto,palabras_clave")
    return sorted(filas, key=lambda o: (o["tipo"] != "especifica", o["numero"]))


def titulo_corto(texto: str, palabras: int = 6) -> str:
    partes = (texto or "").split()
    corto = " ".join(partes[:palabras])
    corto = corto[:1].upper() + corto[1:].lower()
    return corto + ("…" if len(partes) > palabras else "")


def informe_propio(user_id: str, informe_id: str) -> dict:
    i = get_db().uno("informes", {"id": informe_id, "user_id": user_id})
    if not i:
        raise no_encontrado("El informe")
    return i


def actividad_propia(user_id: str, actividad_id: str) -> dict:
    a = get_db().uno("actividades", {"id": actividad_id, "user_id": user_id})
    if not a:
        raise no_encontrado("La actividad")
    return a


def validar_obligacion(contrato_id: str, obligacion_id: str) -> dict:
    o = get_db().uno("obligaciones", {"id": obligacion_id, "contrato_id": contrato_id})
    if not o:
        raise ErrorApi(400, "obligacion_invalida", "La obligación elegida no pertenece a tu contrato activo.")
    return o


def informe_para_fecha(contrato: dict, user_id: str, fecha: date) -> dict:
    """Informe del periodo que contiene 'fecha'; lo crea si no existe."""
    db = get_db()
    ini, fin = periodos.limites(fecha, contrato)
    existente = db.uno("informes", {"contrato_id": contrato["id"], "periodo_inicio": ini.isoformat(),
                                    "periodo_fin": fin.isoformat()})
    if existente:
        return existente
    # Informe del mismo mes creado antes de que cambiaran las fechas del contrato: se ajusta
    mes_ini = fecha.replace(day=1)
    mes_fin = fecha.replace(day=calendar.monthrange(fecha.year, fecha.month)[1])
    del_mes = db.select("informes", {"contrato_id": contrato["id"], "periodo_inicio": Op("gte", mes_ini.isoformat()),
                                     "periodo_fin": Op("lte", mes_fin.isoformat())}, limite=1)
    if del_mes:
        return db.actualizar("informes", {"id": del_mes[0]["id"]},
                             {"periodo_inicio": ini.isoformat(), "periodo_fin": fin.isoformat()})[0]
    filas, conflicto = db.insertar_o_conflicto("informes", {
        "contrato_id": contrato["id"], "user_id": user_id,
        "periodo_inicio": ini.isoformat(), "periodo_fin": fin.isoformat()})
    if conflicto:  # otra petición lo creó al mismo tiempo
        return db.uno("informes", {"contrato_id": contrato["id"], "periodo_inicio": ini.isoformat(),
                                   "periodo_fin": fin.isoformat()})
    return filas[0]


def plantilla_activa(user_id: str) -> dict | None:
    """La plantilla propia confirmada del usuario o, si no tiene, la global vigente."""
    db = get_db()
    propia = db.select("plantillas_informe", {"user_id": user_id, "alcance": "usuario", "activa": True},
                       orden="created_at.desc", limite=1)
    if propia:
        return propia[0]
    globales = db.select("plantillas_informe", {"alcance": "global", "activa": True},
                         orden="created_at.desc", limite=1)
    return globales[0] if globales else None
