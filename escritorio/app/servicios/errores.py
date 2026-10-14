"""Error único que ven las pantallas, venga del backend, de Supabase Auth o de la red."""


class ErrorApp(Exception):
    esperado = True  # no ensucia el log: es un error de negocio o de red ya explicado

    def __init__(self, mensaje: str, codigo: str = "error", status: int = 0, datos: dict | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.status = status
        self.datos = datos or {}

    def __str__(self) -> str:
        return self.mensaje


SIN_CONEXION = ("No pudimos conectarnos con el servidor. Revisa tu conexión a internet "
                "(o que el backend esté encendido) e intenta de nuevo.")
SERVIDOR_NO_DISPONIBLE = ("El servidor no está disponible en este momento. Tus datos están a salvo; intenta de nuevo "
                          "en unos minutos y, si sigue igual, avisa a quien te compartió el programa.")
SIN_BACKEND_LOCAL = ("El servidor local (backend) está apagado. Ábrelo con «iniciar_todo.bat» o "
                     "«backend\\iniciar_backend.bat», deja esa ventana abierta e intenta de nuevo.")


SIN_BACKEND_INTEGRADO = ("El servidor interno del programa dejó de responder. Cierra el programa y ábrelo de nuevo.")


def mensaje_sin_conexion(base_url: str) -> str:
    """En este PC (127.0.0.1 / localhost) el problema casi siempre es que el backend no está encendido."""
    if not any(h in base_url for h in ("127.0.0.1", "localhost")):
        return SIN_CONEXION
    from app import config
    return SIN_BACKEND_INTEGRADO if config.MODO_BACKEND == "integrado" else SIN_BACKEND_LOCAL
