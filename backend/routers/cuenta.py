"""Eliminación de la cuenta y sus archivos (Ley 1581 de 2012, habeas data)."""
import logging

from fastapi import APIRouter, Depends

from auth import Usuario, usuario_actual
from db import get_db

log = logging.getLogger("portal.cuenta")
router = APIRouter(tags=["cuenta"])

BUCKETS = ("minutas", "plantillas", "informes", "evidencias")


@router.delete("/cuenta")
def eliminar_cuenta(u: Usuario = Depends(usuario_actual)):
    """Borra los archivos del usuario en Storage y su usuario de Auth (las tablas se borran en cascada)."""
    db = get_db()
    for bucket in BUCKETS:
        rutas = db.listar_recursivo(bucket, u.id)
        if rutas:
            db.borrar_archivos(bucket, rutas)
    db.borrar_usuario(u.id)
    log.info("Cuenta eliminada: %s", u.id)
    return {"ok": True}
