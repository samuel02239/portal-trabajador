"""Estado compartido del programa: sesión, perfil, contrato, plan y periodo elegido.

Las pantallas escuchan sus señales para refrescarse cuando algo cambia.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QObject, QSettings, Signal

from app import config
from app.servicios.api_cliente import ClienteApi
from app.servicios.auth_supabase import AuthSupabase
from app.servicios.sesion import GestorSesion, Sesion


class Estado(QObject):
    sesion_cambiada = Signal()
    perfil_cambiado = Signal()
    contrato_cambiado = Signal()
    actividades_cambiadas = Signal()
    suscripcion_cambiada = Signal()
    periodo_cambiado = Signal(str)

    def __init__(self):
        super().__init__()
        self.auth = AuthSupabase(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        self.gestor = GestorSesion(self.auth)
        self.api = ClienteApi(config.API_BASE_URL, self.gestor)
        self.ajustes = QSettings(config.APP_ORG, "PortalTrabajador")
        self.perfil: dict = {}
        self.contrato: dict | None = None
        self.obligaciones: list[dict] = []
        self.suscripcion: dict | None = None
        self.periodo: str | None = None  # 'YYYY-MM' elegido en Mi informe / Generar

    # --------------------------------------------------------------- sesión
    @property
    def sesion(self) -> Sesion | None:
        return self.gestor.sesion

    def iniciar_sesion(self, sesion: Sesion) -> None:
        self.gestor.establecer(sesion)
        self.sesion_cambiada.emit()

    def cerrar_sesion(self) -> None:
        if self.gestor.sesion:
            self.auth.cerrar(self.gestor.sesion.access_token)
        self.gestor.establecer(None)
        self.perfil, self.contrato, self.obligaciones, self.suscripcion, self.periodo = {}, None, [], None, None
        self.sesion_cambiada.emit()

    # ---------------------------------------------------------------- datos
    def cargar_perfil(self) -> dict:
        """Se llama desde un hilo. Lee el perfil propio en Supabase (RLS)."""
        s = self.gestor.sesion
        token = self.gestor.token()
        self.perfil = self.auth.perfil(token, s.user_id) if s else {}
        return self.perfil

    def poner_contrato(self, datos: dict) -> None:
        self.contrato = datos.get("contrato")
        self.obligaciones = datos.get("obligaciones") or []
        self.contrato_cambiado.emit()

    def poner_suscripcion(self, datos: dict | None) -> None:
        if datos:
            self.suscripcion = datos
            self.suscripcion_cambiada.emit()

    def especificas(self) -> list[dict]:
        return [o for o in self.obligaciones if o.get("tipo") == "especifica"]

    def poner_periodo(self, clave: str) -> None:
        if clave and clave != self.periodo:
            self.periodo = clave
            self.periodo_cambiado.emit(clave)

    def nombre_corto(self) -> str:
        nombre = (self.perfil.get("nombre_completo") or "").strip()
        return nombre.split()[0].capitalize() if nombre else ""

    # ------------------------------------------------------------ ajustes
    def modo_tema(self) -> str:
        return str(self.ajustes.value("tema", "sistema"))

    def guardar_modo_tema(self, modo: str) -> None:
        self.ajustes.setValue("tema", modo)


def hoy() -> date:
    return date.today()


_estado: Estado | None = None


def estado() -> Estado:
    global _estado
    if _estado is None:
        _estado = Estado()
    return _estado
