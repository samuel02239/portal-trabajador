"""Backend del Portal del Trabajador: API en JSON (sin páginas).

Correr en desarrollo:  python main.py   (escucha en http://127.0.0.1:8000)
En el servidor: Dockerfile (uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers). Ver DESPLIEGUE.md.
"""
import logging
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

import config
import errores
from config import cfg
from ia import estado_llaves, ia_configurada
from routers import actividades, contratos, cuenta, informes, pagos, planes, plantillas
from servicios import conversor_pdf, pasarela_wompi, seguridad

VERSION = "1.1.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for aviso in config.revisar():
    logging.getLogger("portal.config").warning(aviso)

app = FastAPI(title="Portal del Trabajador", version=VERSION, docs_url=None, redoc_url=None, openapi_url=None)
errores.registrar(app)
seguridad.registrar(app)

for r in (contratos, actividades, informes, plantillas, planes, pagos, cuenta):
    app.include_router(r.router, prefix="/api")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "servicio": "portal-trabajador",
        "version": VERSION,
        "supabase": bool(cfg.supabase_url and cfg.supabase_service_key),
        "ia_configurada": ia_configurada(),
        "ia_llaves": estado_llaves(),
        "pdf": conversor_pdf.motor(),
        "pagos": pasarela_wompi.configurado(),
        "pagos_entorno": cfg.wompi_env,
        "avisos_configuracion": config.revisar(),  # nombres de variables mal puestas, nunca sus valores
        # El programa de escritorio compara su versión con esta y avisa si hay que actualizar
        "escritorio": {"version_minima": cfg.version_minima_escritorio, "url_descarga": cfg.url_descarga_escritorio},
    }


_PAGINA_CONFIRMADO = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Portal del Trabajador</title>
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:16px;
font-family:"Segoe UI",Arial,sans-serif;background:#f3f5f7;color:#1f2933}
main{background:#fff;border-radius:8px;padding:32px;max-width:440px;box-shadow:0 1px 3px rgba(0,0,0,.12)}
h1{margin:0 0 12px;font-size:22px;color:#0e5a6b}p{line-height:1.5;margin:8px 0}#error{display:none}
</style></head><body><main>
<div id="ok"><h1>Tu correo quedó confirmado</h1>
<p>Vuelve al programa <b>Portal del Trabajador</b> e inicia sesión con tu correo y tu contraseña.</p>
<p>Ya puedes cerrar esta ventana.</p></div>
<div id="error"><h1>El enlace ya no sirve</h1>
<p>Puede que ya lo hayas usado o que haya vencido. Abre el programa e intenta iniciar sesión; si te pide
confirmar el correo, regístrate de nuevo con el mismo correo para recibir otro enlace.</p></div>
</main><script>
if (/error/.test(location.hash + location.search)) {
  document.getElementById("ok").style.display = "none";
  document.getElementById("error").style.display = "block";
}
</script></body></html>"""


@app.get("/confirmado", response_class=HTMLResponse, include_in_schema=False)
def correo_confirmado():
    """Página a la que llega el enlace de confirmación del correo (Site URL de Supabase Auth)."""
    return HTMLResponse(_PAGINA_CONFIRMADO, headers={
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")),
                reload=False)
