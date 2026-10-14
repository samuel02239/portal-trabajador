"""Publica la plantilla oficial (GDOGC01-F007) como plantilla global para todos los usuarios.

Uso:  python scripts/cargar_plantilla_global.py [ruta.docx]
Usa la llave secreta del backend (service role). Calcula el mapa de campos,
sube el archivo a plantillas/global/ y desactiva la global anterior.
"""
import sys
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from db import get_db  # noqa: E402
from servicios import mapa_plantilla  # noqa: E402
from servicios.extractor import TIPOS_MIME, nombre_seguro, validar_archivo  # noqa: E402


def main():
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "plantillas_base" / "GDOGC01-F007.docx"
    contenido = ruta.read_bytes()
    validar_archivo(ruta.name, contenido, {"docx"})
    mapa = mapa_plantilla.detectar(contenido)
    falta = mapa_plantilla.faltantes(mapa)
    if falta:
        sys.exit(f"La plantilla no tiene todos los campos obligatorios: {falta}")
    db = get_db()
    plantilla_id = str(uuid.uuid4())
    destino = f"global/{plantilla_id}.docx"
    db.subir("plantillas", destino, contenido, TIPOS_MIME["docx"])
    db.actualizar("plantillas_informe", {"alcance": "global", "activa": True}, {"activa": False})
    db.insertar("plantillas_informe", {"id": plantilla_id, "alcance": "global", "user_id": None,
                                       "nombre": nombre_seguro(ruta.name), "formato": "docx",
                                       "archivo_path": destino, "mapa_campos": mapa, "activa": True})
    print(f"Plantilla global publicada: {plantilla_id}")
    for fila in mapa_plantilla.resumen(mapa):
        print(f"  {'OK ' if fila['ok'] else '-- '} {fila['nombre']}: {fila['ubicacion']}")


if __name__ == "__main__":
    main()
