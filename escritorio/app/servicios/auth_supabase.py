"""Supabase desde el programa: iniciar sesión y leer/editar datos propios (con RLS).

Usa la API REST de Supabase (Auth y PostgREST) con la llave pública. Hace lo
mismo que supabase-py para estos casos, con menos dependencias en el .exe.
"""
from __future__ import annotations

import httpx

from app.servicios.errores import SIN_CONEXION, ErrorApp
from app.servicios.sesion import Sesion

_MENSAJES = {
    "invalid_credentials": "Correo o contraseña incorrectos.",
    "invalid_grant": "Correo o contraseña incorrectos.",
    "email_not_confirmed": "Confirma tu correo antes de entrar: revisa tu bandeja de entrada (y la de spam).",
    "user_already_exists": "Ya existe una cuenta con ese correo. Inicia sesión.",
    "email_exists": "Ya existe una cuenta con ese correo. Inicia sesión.",
    "weak_password": "La contraseña es muy débil. Usa al menos 8 caracteres con letras y números.",
    "over_email_send_rate_limit": "Se enviaron demasiados correos. Espera unos minutos e intenta de nuevo.",
    "over_request_rate_limit": "Demasiados intentos. Espera unos minutos e intenta de nuevo.",
    "otp_expired": "El código no es válido o ya venció. Pide uno nuevo.",
    "refresh_token_not_found": "Tu sesión terminó. Vuelve a iniciar sesión.",
    "refresh_token_already_used": "Tu sesión terminó. Vuelve a iniciar sesión.",
    "session_not_found": "Tu sesión terminó. Vuelve a iniciar sesión.",
    "email_address_invalid": "Ese correo no es válido.",
    "signup_disabled": "El registro de cuentas nuevas está deshabilitado.",
}


def _error_de(r: httpx.Response) -> ErrorApp:
    try:
        d = r.json()
    except ValueError:
        d = {}
    codigo = d.get("error_code") or d.get("error") or ""
    texto = (d.get("msg") or d.get("error_description") or d.get("message") or "").lower()
    if codigo in _MENSAJES:
        mensaje = _MENSAJES[codigo]
    elif "invalid login" in texto:
        mensaje, codigo = _MENSAJES["invalid_credentials"], "invalid_credentials"
    elif "not confirmed" in texto:
        mensaje, codigo = _MENSAJES["email_not_confirmed"], "email_not_confirmed"
    elif "already registered" in texto:
        mensaje, codigo = _MENSAJES["user_already_exists"], "user_already_exists"
    elif "password" in texto and ("least" in texto or "weak" in texto):
        mensaje, codigo = _MENSAJES["weak_password"], "weak_password"
    elif "expired" in texto or "invalid" in texto and "token" in texto:
        mensaje, codigo = _MENSAJES["otp_expired"], "otp_expired"
    elif r.status_code == 429:
        mensaje, codigo = _MENSAJES["over_request_rate_limit"], "rate_limit"
    else:
        mensaje = "No se pudo completar la operación con el servicio de cuentas. Intenta de nuevo."
    return ErrorApp(mensaje, codigo or "auth", r.status_code)


class AuthSupabase:
    def __init__(self, url: str, llave_publica: str):
        self.url = url.rstrip("/")
        self.llave = llave_publica
        self.http = httpx.Client(timeout=httpx.Timeout(25.0, connect=10.0), headers={"apikey": llave_publica})

    def _post(self, ruta: str, json: dict, token: str | None = None, metodo: str = "POST") -> dict:
        cab = {"Authorization": f"Bearer {token or self.llave}"}
        try:
            r = self.http.request(metodo, f"{self.url}/auth/v1/{ruta}", json=json, headers=cab)
        except httpx.HTTPError as exc:
            raise ErrorApp(SIN_CONEXION, "sin_conexion") from exc
        if r.status_code >= 400:
            raise _error_de(r)
        return r.json() if r.content else {}

    # ---------------------------------------------------------------- cuentas
    def registrar(self, email: str, password: str, nombre: str) -> Sesion | None:
        """Crea la cuenta. Devuelve la sesión si no hace falta confirmar el correo; si no, None."""
        d = self._post("signup", {"email": email, "password": password, "data": {"nombre_completo": nombre}})
        if d.get("access_token"):
            return Sesion.desde_gotrue(d)
        if isinstance(d.get("identities"), list) and not d["identities"]:
            raise ErrorApp(_MENSAJES["user_already_exists"], "user_already_exists", 400)
        return None

    def iniciar(self, email: str, password: str) -> Sesion:
        return Sesion.desde_gotrue(self._post("token?grant_type=password", {"email": email, "password": password}))

    def refrescar(self, refresh_token: str) -> Sesion:
        return Sesion.desde_gotrue(self._post("token?grant_type=refresh_token", {"refresh_token": refresh_token}))

    def recuperar(self, email: str) -> None:
        self._post("recover", {"email": email})

    def verificar_recuperacion(self, email: str, codigo: str) -> Sesion:
        return Sesion.desde_gotrue(self._post("verify", {"type": "recovery", "email": email, "token": codigo}))

    def cambiar_password(self, token: str, nueva: str) -> None:
        self._post("user", {"password": nueva}, token=token, metodo="PUT")

    def cerrar(self, token: str) -> None:
        try:
            self._post("logout", {}, token=token)
        except ErrorApp:
            pass  # si ya venció, igual se borra localmente

    # -------------------------------------------------- datos propios (RLS)
    def _rest(self, metodo: str, tabla: str, token: str, params: dict, json: dict | None = None) -> list:
        cab = {"Authorization": f"Bearer {token}", "Prefer": "return=representation"}
        try:
            r = self.http.request(metodo, f"{self.url}/rest/v1/{tabla}", params=params, json=json, headers=cab)
        except httpx.HTTPError as exc:
            raise ErrorApp(SIN_CONEXION, "sin_conexion") from exc
        if r.status_code >= 400:
            raise ErrorApp("No se pudieron leer tus datos. Intenta de nuevo.", "rest", r.status_code)
        return r.json() if r.content else []

    def perfil(self, token: str, user_id: str) -> dict:
        filas = self._rest("GET", "profiles", token, {"id": f"eq.{user_id}", "select": "*"})
        return filas[0] if filas else {}

    def actualizar_perfil(self, token: str, user_id: str, nombre: str) -> dict:
        """Solo el nombre: la cédula la fija el servidor al registrar el contrato (una cédula = una cuenta)."""
        filas = self._rest("PATCH", "profiles", token, {"id": f"eq.{user_id}"}, {"nombre_completo": nombre})
        return filas[0] if filas else {}

    def pagos(self, token: str) -> list[dict]:
        return self._rest("GET", "pagos", token, {"select": "referencia,plan_id,monto_cop,estado,created_at",
                                                  "order": "created_at.desc", "limit": "50"})
