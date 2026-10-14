"""Planes y estado de la suscripción."""
from fastapi import APIRouter, Depends

from auth import Usuario, usuario_actual
from db import get_db
from servicios import cupo

router = APIRouter(tags=["planes"])


@router.get("/planes")
def listar_planes(u: Usuario = Depends(usuario_actual)):
    planes = get_db().select("planes", {"activo": True}, orden="precio_cop.asc")
    return {"planes": planes}


@router.get("/suscripcion/actual")
def suscripcion_actual(u: Usuario = Depends(usuario_actual)):
    return cupo.estado(u.id)
