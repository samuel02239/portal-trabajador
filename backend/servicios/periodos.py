"""Periodos mensuales del informe, recortados al plazo del contrato."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone

COLOMBIA = timezone(timedelta(hours=-5))  # Colombia no tiene horario de verano

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def hoy() -> date:
    return datetime.now(COLOMBIA).date()


def a_fecha(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def fecha_larga(d: date) -> str:
    return f"{d.day:02d} de {MESES[d.month - 1]} de {d.year}"


def clave(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def etiqueta(anio: int, mes: int) -> str:
    return f"{MESES[mes - 1].capitalize()} {anio}"


def desde_clave(c: str) -> date:
    anio, mes = c.split("-")
    return date(int(anio), int(mes), 1)


def limites(fecha: date, contrato: dict) -> tuple[date, date]:
    """Periodo (inicio, fin) del mes de 'fecha', recortado a las fechas del contrato si caen dentro."""
    ini = fecha.replace(day=1)
    fin = fecha.replace(day=calendar.monthrange(fecha.year, fecha.month)[1])
    c_ini, c_fin = a_fecha(contrato.get("fecha_inicio")), a_fecha(contrato.get("fecha_fin"))
    if c_ini and ini < c_ini <= fin:
        ini = c_ini
    if c_fin and ini <= c_fin < fin:
        fin = c_fin
    return ini, fin


def fuera_del_contrato(inicio: date, fin: date, contrato: dict) -> bool:
    c_ini, c_fin = a_fecha(contrato.get("fecha_inicio")), a_fecha(contrato.get("fecha_fin"))
    return bool((c_ini and fin < c_ini) or (c_fin and inicio > c_fin))


def lista(contrato: dict, extras: list[str] | None = None) -> list[dict]:
    """Meses disponibles para elegir: los del plazo del contrato (o los últimos 6) más los que ya tienen informe."""
    c_ini, c_fin = a_fecha(contrato.get("fecha_inicio")), a_fecha(contrato.get("fecha_fin"))
    actual = hoy().replace(day=1)
    meses: set[str] = set(extras or [])
    if c_ini and c_fin:
        d = c_ini.replace(day=1)
        tope = c_fin.replace(day=1)
        while d <= tope and len(meses) < 36:
            meses.add(clave(d))
            d = (d + timedelta(days=32)).replace(day=1)
    else:
        d = actual
        for _ in range(6):
            meses.add(clave(d))
            d = (d - timedelta(days=1)).replace(day=1)
    meses.add(clave(actual))
    return [{"clave": c, "etiqueta": etiqueta(int(c[:4]), int(c[5:]))} for c in sorted(meses)]
