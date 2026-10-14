"""Acceso a Supabase (PostgREST, Storage y Auth) con la llave secreta del backend.

Se usa httpx directamente: funciona igual con las llaves nuevas (sb_secret_...)
y con las antiguas (service_role JWT). La llave va en los encabezados apikey y
Authorization, como pide la documentación de Supabase.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from config import cfg
from errores import ErrorApi

log = logging.getLogger("portal.db")


class Op:
    """Filtro con operador explícito de PostgREST: Op('lte', '2026-10-01')."""

    def __init__(self, operador: str, valor: Any):
        self.operador = operador
        self.valor = valor


def _valor(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    return str(v)


def _filtros(filtros: dict | None) -> dict[str, str]:
    params: dict[str, str] = {}
    for col, v in (filtros or {}).items():
        if isinstance(v, Op):
            params[col] = f"{v.operador}.{_valor(v.valor)}"
        elif isinstance(v, (list, tuple, set)):
            params[col] = "in.(" + ",".join(_valor(x) for x in v) + ")"
        elif v is None:
            params[col] = "is.null"
        else:
            params[col] = f"eq.{_valor(v)}"
    return params


class Supabase:
    def __init__(self, url: str, llave: str, llave_publica: str = ""):
        self.url = url.rstrip("/")
        self.llave = llave
        self.llave_publica = llave_publica or llave
        self.http = httpx.Client(timeout=httpx.Timeout(40.0, connect=10.0),
                                 headers={"apikey": llave, "Authorization": f"Bearer {llave}"})

    # ------------------------------------------------------------------ util
    def _revisar(self, r: httpx.Response, que: str) -> httpx.Response:
        if r.status_code >= 400:
            log.warning("Supabase %s -> HTTP %s: %s", que, r.status_code, r.text[:300])
            raise ErrorApi(502, "error_base_datos",
                           "No pudimos comunicarnos con la base de datos. Intenta de nuevo.",
                           detalle=f"{que}: HTTP {r.status_code}")
        return r

    # ------------------------------------------------------------- PostgREST
    def select(self, tabla: str, filtros: dict | None = None, columnas: str = "*",
               orden: str | None = None, limite: int | None = None) -> list[dict]:
        params = _filtros(filtros)
        params["select"] = columnas
        if orden:
            params["order"] = orden
        if limite:
            params["limit"] = str(limite)
        r = self.http.get(f"{self.url}/rest/v1/{tabla}", params=params)
        return self._revisar(r, f"select {tabla}").json()

    def uno(self, tabla: str, filtros: dict, columnas: str = "*") -> dict | None:
        filas = self.select(tabla, filtros, columnas, limite=1)
        return filas[0] if filas else None

    def insertar(self, tabla: str, filas: dict | list[dict]) -> list[dict]:
        r = self.http.post(f"{self.url}/rest/v1/{tabla}", json=filas,
                           headers={"Prefer": "return=representation"})
        return self._revisar(r, f"insert {tabla}").json()

    def insertar_o_conflicto(self, tabla: str, fila: dict) -> tuple[list[dict], bool]:
        """Inserta; devuelve (filas, hubo_conflicto) sin lanzar error si choca con un índice único."""
        r = self.http.post(f"{self.url}/rest/v1/{tabla}", json=fila,
                           headers={"Prefer": "return=representation"})
        if r.status_code == 409:
            return [], True
        return self._revisar(r, f"insert {tabla}").json(), False

    def actualizar(self, tabla: str, filtros: dict, valores: dict) -> list[dict]:
        if not filtros:
            raise ValueError("actualizar sin filtros no está permitido")
        r = self.http.patch(f"{self.url}/rest/v1/{tabla}", params=_filtros(filtros), json=valores,
                            headers={"Prefer": "return=representation"})
        return self._revisar(r, f"update {tabla}").json()

    def borrar(self, tabla: str, filtros: dict) -> list[dict]:
        if not filtros:
            raise ValueError("borrar sin filtros no está permitido")
        r = self.http.delete(f"{self.url}/rest/v1/{tabla}", params=_filtros(filtros),
                             headers={"Prefer": "return=representation"})
        return self._revisar(r, f"delete {tabla}").json()

    def rpc(self, funcion: str, params: dict) -> Any:
        r = self.http.post(f"{self.url}/rest/v1/rpc/{funcion}", json=params)
        return self._revisar(r, f"rpc {funcion}").json()

    # --------------------------------------------------------------- Storage
    @staticmethod
    def _ruta(ruta: str) -> str:
        return quote(ruta, safe="/")

    def subir(self, bucket: str, ruta: str, contenido: bytes, tipo: str) -> None:
        r = self.http.post(f"{self.url}/storage/v1/object/{bucket}/{self._ruta(ruta)}", content=contenido,
                           headers={"Content-Type": tipo, "x-upsert": "true"}, timeout=120)
        self._revisar(r, f"subir {bucket}")

    def descargar(self, bucket: str, ruta: str) -> bytes:
        r = self.http.get(f"{self.url}/storage/v1/object/{bucket}/{self._ruta(ruta)}", timeout=120)
        return self._revisar(r, f"descargar {bucket}").content

    def mover(self, bucket: str, origen: str, destino: str) -> None:
        r = self.http.post(f"{self.url}/storage/v1/object/move",
                           json={"bucketId": bucket, "sourceKey": origen, "destinationKey": destino})
        self._revisar(r, f"mover {bucket}")

    def url_firmada(self, bucket: str, ruta: str, segundos: int = 300, descarga: str | None = None) -> str:
        r = self.http.post(f"{self.url}/storage/v1/object/sign/{bucket}/{self._ruta(ruta)}",
                           json={"expiresIn": segundos})
        firmada = self._revisar(r, f"firmar {bucket}").json()["signedURL"]
        url = f"{self.url}/storage/v1{firmada}"
        if descarga:
            url += "&download=" + quote(descarga)
        return url

    def borrar_archivos(self, bucket: str, rutas: list[str]) -> None:
        for i in range(0, len(rutas), 100):
            r = self.http.request("DELETE", f"{self.url}/storage/v1/object/{bucket}",
                                  json={"prefixes": rutas[i:i + 100]})
            self._revisar(r, f"borrar {bucket}")

    def listar_recursivo(self, bucket: str, prefijo: str) -> list[str]:
        """Todas las rutas de archivos bajo un prefijo (carpeta) de un bucket."""
        rutas: list[str] = []
        pendientes = [prefijo.strip("/")]
        while pendientes:
            carpeta = pendientes.pop()
            r = self.http.post(f"{self.url}/storage/v1/object/list/{bucket}",
                               json={"prefix": carpeta, "limit": 1000, "offset": 0})
            for item in self._revisar(r, f"listar {bucket}").json():
                ruta = f"{carpeta}/{item['name']}" if carpeta else item["name"]
                if item.get("id") is None:  # es una carpeta
                    pendientes.append(ruta)
                else:
                    rutas.append(ruta)
        return rutas

    # ------------------------------------------------------------------ Auth
    def usuario_de_token(self, token: str) -> dict | None:
        r = self.http.get(f"{self.url}/auth/v1/user",
                          headers={"apikey": self.llave_publica, "Authorization": f"Bearer {token}"})
        if r.status_code in (401, 403):
            return None
        return self._revisar(r, "auth user").json()

    def borrar_usuario(self, user_id: str) -> None:
        r = self.http.delete(f"{self.url}/auth/v1/admin/users/{user_id}")
        self._revisar(r, "borrar usuario")

    def crear_usuario(self, email: str, password: str, nombre: str = "") -> dict:
        """Solo para scripts de prueba: crea un usuario ya confirmado."""
        r = self.http.post(f"{self.url}/auth/v1/admin/users",
                           json={"email": email, "password": password, "email_confirm": True,
                                 "user_metadata": {"nombre_completo": nombre}})
        return self._revisar(r, "crear usuario").json()


_db: Supabase | None = None


def get_db() -> Supabase:
    global _db
    if _db is None:
        if not cfg.supabase_url or not cfg.supabase_service_key:
            raise ErrorApi(500, "configuracion", "Falta SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en backend/.env.")
        _db = Supabase(cfg.supabase_url, cfg.supabase_service_key, cfg.supabase_anon_key)
    return _db
