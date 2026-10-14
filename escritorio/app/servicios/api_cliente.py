"""Cliente del backend (httpx). Toda regla de negocio la decide el backend."""
from __future__ import annotations

import mimetypes
from pathlib import Path

import httpx

from app.servicios.errores import SIN_CONEXION, ErrorApp, mensaje_sin_conexion


class ClienteApi:
    def __init__(self, base_url: str, gestor_sesion):
        self.base = base_url.rstrip("/") + "/api"
        self.sesion = gestor_sesion
        self.http = httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))

    def cambiar_base(self, base_url: str) -> None:
        """El backend integrado puede quedar en otro puerto si el 8000 está ocupado."""
        self.base = base_url.rstrip("/") + "/api"

    # ----------------------------------------------------------------- base
    def _cabeceras(self, forzar: bool = False) -> dict:
        token = self.sesion.token(forzar=forzar)
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _solicitud(self, metodo: str, ruta: str, timeout: float | None = None, **kw):
        for intento in (1, 2):
            try:
                r = self.http.request(metodo, self.base + ruta, headers=self._cabeceras(forzar=intento == 2),
                                      timeout=timeout or httpx.USE_CLIENT_DEFAULT, **kw)
            except httpx.TimeoutException as exc:
                raise ErrorApp("El servidor tardó demasiado en responder. Intenta de nuevo.", "tiempo_agotado") from exc
            except httpx.HTTPError as exc:
                raise ErrorApp(mensaje_sin_conexion(self.base), "sin_conexion") from exc
            if r.status_code == 401 and intento == 1 and self.sesion.sesion:
                continue  # el token venció: se renueva y se repite una vez
            break
        if r.status_code >= 400:
            try:
                err = r.json().get("error") or {}
            except ValueError:
                err = {}
            datos = {k: v for k, v in err.items() if k not in ("codigo", "mensaje")}
            raise ErrorApp(err.get("mensaje") or f"El servidor respondió con un error ({r.status_code}).",
                           err.get("codigo") or "error_http", r.status_code, datos)
        return r.json() if r.content else {}

    def _archivo(self, ruta_api: str, archivo: str | Path, campo: str = "archivo", datos: dict | None = None,
                 timeout: float = 180):
        ruta = Path(archivo)
        tipo = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
        with open(ruta, "rb") as f:
            return self._solicitud("POST", ruta_api, timeout=timeout, files={campo: (ruta.name, f, tipo)},
                                   data=datos or {})

    # ------------------------------------------------------------ servicio
    def health(self) -> dict:
        return self._solicitud("GET", "/health", timeout=8)

    # ------------------------------------------------------------ contrato
    def contrato_actual(self) -> dict:
        return self._solicitud("GET", "/contratos/actual")

    def leer_minuta(self, archivo: str) -> dict:
        return self._archivo("/contratos/minuta", archivo, timeout=240)

    def guardar_contrato(self, datos: dict) -> dict:
        return self._solicitud("POST", "/contratos", json=datos)

    def editar_contrato(self, contrato_id: str, datos: dict) -> dict:
        return self._solicitud("PUT", f"/contratos/{contrato_id}", json=datos)

    # ----------------------------------------------------------- actividades
    def clasificar(self, texto: str, fecha: str) -> dict:
        return self._solicitud("POST", "/actividades/clasificar", json={"texto": texto, "fecha": fecha}, timeout=200)

    def crear_actividad(self, datos: dict) -> dict:
        return self._solicitud("POST", "/actividades", json=datos)

    def editar_actividad(self, actividad_id: str, cambios: dict) -> dict:
        return self._solicitud("PATCH", f"/actividades/{actividad_id}", json=cambios)

    def borrar_actividad(self, actividad_id: str) -> dict:
        return self._solicitud("DELETE", f"/actividades/{actividad_id}")

    def subir_evidencia(self, actividad_id: str, archivo: str) -> dict:
        return self._archivo(f"/actividades/{actividad_id}/evidencias", archivo)

    def editar_evidencia(self, actividad_id: str, evidencia_id: str, descripcion: str | None = None,
                         regenerar: bool = False) -> dict:
        return self._solicitud("PATCH", f"/actividades/{actividad_id}/evidencias/{evidencia_id}",
                               json={"descripcion": descripcion, "regenerar": regenerar}, timeout=120)

    def borrar_evidencia(self, actividad_id: str, evidencia_id: str) -> dict:
        return self._solicitud("DELETE", f"/actividades/{actividad_id}/evidencias/{evidencia_id}")

    # ------------------------------------------------------------- informes
    def informe_actual(self, periodo: str | None = None) -> dict:
        return self._solicitud("GET", "/informes/actual", params={"periodo": periodo} if periodo else None)

    def generar_informe(self, informe_id: str, tipo: str, fecha_elaboracion: str) -> dict:
        return self._solicitud("POST", f"/informes/{informe_id}/generar",
                               json={"tipo": tipo, "fecha_elaboracion": fecha_elaboracion}, timeout=300)

    def url_descarga(self, informe_id: str, formato: str) -> dict:
        return self._solicitud("GET", f"/informes/{informe_id}/descargar", params={"formato": formato})

    def descargar(self, url: str) -> bytes:
        try:
            r = self.http.get(url, timeout=120)
        except httpx.HTTPError as exc:
            raise ErrorApp(SIN_CONEXION, "sin_conexion") from exc
        if r.status_code >= 400:
            raise ErrorApp("El enlace de descarga venció. Intenta de nuevo.", "descarga", r.status_code)
        return r.content

    def descargar_informe(self, informe_id: str, formato: str) -> tuple[str, bytes]:
        d = self.url_descarga(informe_id, formato)
        return d["nombre"], self.descargar(d["url"])

    # ------------------------------------------------------------ plantillas
    def plantilla_actual(self) -> dict:
        return self._solicitud("GET", "/plantillas/actual")

    def subir_plantilla(self, archivo: str) -> dict:
        return self._archivo("/plantillas", archivo, datos={"alcance": "usuario"})

    def confirmar_plantilla(self, plantilla_id: str, mapa: dict | None = None) -> dict:
        return self._solicitud("POST", f"/plantillas/{plantilla_id}/confirmar", json={"mapa_campos": mapa})

    def quitar_plantilla(self, plantilla_id: str) -> dict:
        return self._solicitud("DELETE", f"/plantillas/{plantilla_id}")

    # ------------------------------------------------------ planes y pagos
    def planes(self) -> dict:
        return self._solicitud("GET", "/planes")

    def suscripcion(self) -> dict:
        return self._solicitud("GET", "/suscripcion/actual")

    def checkout(self, plan_id: str) -> dict:
        return self._solicitud("POST", "/pagos/checkout", json={"plan_id": plan_id})

    def estado_pago(self, referencia: str) -> dict:
        return self._solicitud("GET", f"/pagos/{referencia}", timeout=30)

    # ---------------------------------------------------------------- cuenta
    def eliminar_cuenta(self) -> dict:
        return self._solicitud("DELETE", "/cuenta", timeout=120)
