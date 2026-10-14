"""Alertas útiles del informe (sección 7.4)."""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from servicios import periodos


def _norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()


def _f(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "?"


def calcular(contrato: dict, perfil: dict, inicio: date, fin: date,
             obligaciones: list[dict], actividades: list[dict]) -> list[dict]:
    """obligaciones: específicas del contrato. actividades: todas las del informe."""
    alertas: list[dict] = []

    def agregar(nivel: str, codigo: str, mensaje: str, **extra):
        alertas.append({"nivel": nivel, "codigo": codigo, "mensaje": mensaje, **extra})

    # 1. Periodo frente al plazo del contrato
    c_ini = periodos.a_fecha(contrato.get("fecha_inicio"))
    c_fin = periodos.a_fecha(contrato.get("fecha_fin"))
    if not c_ini or not c_fin:
        agregar("advertencia", "contrato_sin_fechas",
                "Tu contrato no tiene fechas de inicio y terminación. Agrégalas en Perfil > Editar datos del contrato.")
    elif periodos.fuera_del_contrato(inicio, fin, contrato):
        agregar("error", "periodo_fuera_del_plazo",
                f"El periodo del informe ({_f(inicio)} al {_f(fin)}) está fuera del plazo del contrato "
                f"({_f(c_ini)} al {_f(c_fin)}).")

    # 2. Obligaciones específicas sin actividades
    con_actividad = {a.get("obligacion_id") for a in actividades
                     if a.get("obligacion_id") and a.get("estado") == "confirmada"}
    for o in obligaciones:
        if o["id"] not in con_actividad:
            agregar("advertencia", "obligacion_sin_actividades",
                    f"La obligación {o['numero']} no tiene actividades en este periodo.", obligacion_id=o["id"])

    # 3. Fechas de actividades fuera del periodo
    fuera = [a for a in actividades
             if not (inicio <= periodos.a_fecha(a["fecha"]) <= fin)]
    if fuera:
        agregar("advertencia", "actividades_fuera_del_periodo",
                f"{len(fuera)} actividad(es) tienen fecha fuera del periodo del informe.",
                actividades=[a["id"] for a in fuera])

    # 4. Datos del informe frente a la minuta
    if not (perfil.get("nombre_completo") or "").strip():
        agregar("error", "falta_nombre", "Falta tu nombre completo. Escríbelo en Perfil.")
    if not (perfil.get("cedula") or "").strip():
        agregar("error", "falta_cedula", "Falta tu número de cédula. Escríbelo en Perfil.")
    contratista = (contrato.get("datos_json") or {}).get("contratista") or {}
    if contratista.get("nombre") and perfil.get("nombre_completo") \
            and _norm(contratista["nombre"]) != _norm(perfil["nombre_completo"]):
        agregar("advertencia", "nombre_no_coincide",
                f"Tu nombre en el perfil ({perfil['nombre_completo']}) no coincide con el de la minuta "
                f"({contratista['nombre']}).")
    if contratista.get("cedula") and perfil.get("cedula") \
            and re.sub(r"\D", "", contratista["cedula"]) != re.sub(r"\D", "", perfil["cedula"]):
        agregar("advertencia", "cedula_no_coincide",
                f"Tu cédula en el perfil ({perfil['cedula']}) no coincide con la de la minuta ({contratista['cedula']}).")
    if not (contrato.get("supervisor_nombre") or "").strip():
        agregar("advertencia", "falta_supervisor",
                "Falta el nombre del supervisor. Agrégalo en Perfil > Editar datos del contrato.")

    # 5. Actividades que no saldrán en el informe
    sin_ubicar = [a for a in actividades if not a.get("obligacion_id")]
    if sin_ubicar:
        agregar("info", "actividades_sin_obligacion",
                f"{len(sin_ubicar)} actividad(es) no están en ninguna obligación y no saldrán en el informe.")
    return alertas
