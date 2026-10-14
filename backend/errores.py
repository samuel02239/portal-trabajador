"""Errores en JSON uniforme: {"error": {"codigo": "...", "mensaje": "..."}}."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("portal")


class ErrorApi(Exception):
    def __init__(self, status: int, codigo: str, mensaje: str, **extra):
        super().__init__(mensaje)
        self.status = status
        self.codigo = codigo
        self.mensaje = mensaje
        self.extra = extra


def no_encontrado(que: str = "El recurso") -> ErrorApi:
    return ErrorApi(404, "no_encontrado", f"{que} no existe o no es tuyo.")


def _respuesta(status: int, codigo: str, mensaje: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"codigo": codigo, "mensaje": mensaje, **extra}})


def registrar(app: FastAPI) -> None:
    @app.exception_handler(ErrorApi)
    async def _error_api(_: Request, exc: ErrorApi):
        return _respuesta(exc.status, exc.codigo, exc.mensaje, **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, exc: RequestValidationError):
        detalles = "; ".join(f"{'.'.join(str(x) for x in e['loc'][1:])}: {e['msg']}" for e in exc.errors()[:5])
        return _respuesta(422, "datos_invalidos", f"Revisa los datos enviados ({detalles}).")

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        codigos = {401: "no_autenticado", 403: "prohibido", 404: "no_encontrado", 405: "metodo_no_permitido"}
        return _respuesta(exc.status_code, codigos.get(exc.status_code, "error_http"), str(exc.detail))

    @app.exception_handler(Exception)
    async def _inesperado(_: Request, exc: Exception):
        log.exception("Error no controlado: %s", type(exc).__name__)
        return _respuesta(500, "error_interno", "Ocurrió un error inesperado. Intenta de nuevo en unos minutos.")
