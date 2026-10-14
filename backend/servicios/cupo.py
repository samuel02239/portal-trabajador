"""Cupo de informes por plan (sección 13). Toda la lógica vive en funciones SQL atómicas."""
from __future__ import annotations

from db import get_db


def estado(user_id: str) -> dict:
    """Plan vigente, usados, restantes (None = ilimitados), ciclo y vencimiento."""
    return get_db().rpc("estado_suscripcion", {"p_user": user_id})


def consumir(user_id: str, informe_id: str) -> dict:
    """{'permitido': bool, 'cobrado': bool, 'plan': str, 'ciclo': str, ...}. Usa un candado por usuario."""
    return get_db().rpc("consumir_informe", {"p_user": user_id, "p_informe": informe_id})


def devolver(user_id: str, informe_id: str, ciclo: str) -> None:
    """Si la generación falla, se borra el consumo (y se devuelve la prueba por cédula) para no cobrar
    un informe que no se entregó."""
    get_db().rpc("devolver_informe", {"p_user": user_id, "p_informe": informe_id, "p_ciclo": ciclo})
