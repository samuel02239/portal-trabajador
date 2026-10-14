"""Ventana principal: barra lateral + pila de pantallas (QStackedWidget).

Navegación tras iniciar sesión: sin contrato -> Subir minuta; con contrato -> Inicio.
"""
from __future__ import annotations

import logging
import time

import qtawesome as qta
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QSizePolicy,
                               QStackedWidget, QVBoxLayout, QWidget)

from app import config, tema
from app.estado import estado
from app.servicios.errores import ErrorApp
from app.servicios.hilos import ejecutar
from app.widgets import dialogos
from app.widgets.carga import Indicador
from app.widgets.medidor_cupo import MedidorCupo

log = logging.getLogger("portal.ventana")
# Un servidor en la nube que estaba dormido (plan gratis) o actualizándose tarda hasta un minuto en responder
ESPERA_SERVIDOR = 75

SECCIONES = [
    ("inicio", "Inicio", "fa6s.house"),
    ("actividad", "Registrar actividad", "fa6s.pen-to-square"),
    ("informe", "Mi informe", "fa6s.list-check"),
    ("generar", "Generar informe", "fa6s.file-export"),
    ("planes", "Planes", "fa6s.credit-card"),
    ("perfil", "Perfil", "fa6s.circle-user"),
]
SESION_TERMINADA = {"sesion_vencida", "no_autenticado", "refresh_token_not_found", "refresh_token_already_used",
                    "session_not_found"}
COLOR_LATERAL = "#D3DCE6"


def iniciales(nombre: str, respaldo: str = "") -> str:
    partes = [p for p in (nombre or "").split() if p]
    if len(partes) >= 2:
        return (partes[0][0] + partes[1][0]).upper()
    if partes:
        return partes[0][:2].upper()
    return (respaldo or "?")[:2].upper()


class EtiquetaElidida(QLabel):
    """Recorta con '…' el texto que no cabe."""

    def __init__(self, texto: str = "", rol: str | None = None):
        super().__init__()
        self._texto = texto
        if rol:
            self.setProperty("rol", rol)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.poner(texto)

    def poner(self, texto: str) -> None:
        self._texto = texto or ""
        self.setToolTip(self._texto)
        self._ajustar()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._ajustar()

    def _ajustar(self) -> None:
        ancho = max(10, self.width())
        self.setText(self.fontMetrics().elidedText(self._texto, Qt.ElideRight, ancho))


class PaginaCargando(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("fondo")
        capa = QVBoxLayout(self)
        capa.setAlignment(Qt.AlignCenter)
        marca = QLabel(config.APP_NOMBRE)
        marca.setProperty("rol", "titulo")
        marca.setAlignment(Qt.AlignCenter)
        self.indicador = Indicador("Abriendo tu sesión…")
        self.indicador.show()
        capa.addWidget(marca)
        capa.addWidget(self.indicador, 0, Qt.AlignCenter)


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.e = estado()
        self.setWindowTitle(config.APP_NOMBRE)
        self.setMinimumSize(1100, 700)
        icono = config.RECURSOS / "icono.png"
        if icono.exists():
            self.setWindowIcon(QIcon(str(icono)))

        from app.ventanas.login import VentanaLogin
        from app.ventanas.minuta import VentanaMinuta
        from app.ventanas.revisar import VentanaRevisar

        self.pila = QStackedWidget()
        self.pila.setObjectName("paginas")
        self.pag_cargando = PaginaCargando()
        self.pag_login = VentanaLogin(self)
        self.pag_minuta = VentanaMinuta(self)
        self.pag_revisar = VentanaRevisar(self)
        self.pag_app = self._crear_app()
        for p in (self.pag_cargando, self.pag_login, self.pag_minuta, self.pag_revisar, self.pag_app):
            self.pila.addWidget(p)
        self.setCentralWidget(self.pila)

        QShortcut(QKeySequence("Ctrl+N"), self, activated=lambda: self._atajo("actividad"))
        QShortcut(QKeySequence("Ctrl+G"), self, activated=lambda: self._atajo("generar"))
        self.e.suscripcion_cambiada.connect(lambda: self.medidor.poner(self.e.suscripcion))
        self.e.perfil_cambiado.connect(self._pintar_usuario)
        QTimer.singleShot(0, self.arrancar)

    # ------------------------------------------------------------ armado
    def _crear_lateral(self) -> QFrame:
        lateral = QFrame()
        lateral.setObjectName("barraLateral")
        lateral.setFixedWidth(236)
        col = QVBoxLayout(lateral)
        col.setContentsMargins(0, 20, 0, 16)
        col.setSpacing(2)

        marca = QHBoxLayout()
        marca.setContentsMargins(18, 0, 14, 0)
        marca.setSpacing(10)
        cuadro = QFrame()
        cuadro.setObjectName("marcaIcono")
        cuadro.setFixedSize(38, 38)
        ci = QVBoxLayout(cuadro)
        ci.setContentsMargins(0, 0, 0, 0)
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setPixmap(qta.icon("fa6s.file-lines", color="#FFFFFF").pixmap(18, 18))
        ci.addWidget(logo)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        nombre = QLabel("Portal del Trabajador")
        nombre.setProperty("rol", "lateralMarca")
        nombre.setWordWrap(True)
        lema = QLabel("INFORMES MENSUALES")
        lema.setProperty("rol", "lateralSec")
        textos.addWidget(nombre)
        textos.addWidget(lema)
        marca.addWidget(cuadro, 0, Qt.AlignTop)
        marca.addLayout(textos, 1)
        col.addLayout(marca)
        col.addSpacing(26)

        menu = QLabel("MENÚ")
        menu.setProperty("rol", "lateralSec")
        menu.setContentsMargins(20, 0, 0, 6)
        col.addWidget(menu)
        self.grupo_nav = QButtonGroup(self)
        self.grupo_nav.setExclusive(True)
        self.botones_nav: dict[str, QPushButton] = {}
        for clave, texto, icono in SECCIONES:
            b = QPushButton(qta.icon(icono, color=COLOR_LATERAL, color_active="#FFFFFF"), f"   {texto}")
            b.setObjectName("navBoton")
            b.setCheckable(True)
            b.setIconSize(QSize(tema.ICONO_MENU, tema.ICONO_MENU))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, c=clave: self.ir(c))
            self.grupo_nav.addButton(b)
            self.botones_nav[clave] = b
            col.addWidget(b)
        col.addStretch(1)

        tarjeta = QFrame()
        tarjeta.setObjectName("usuarioLateral")
        ft = QHBoxLayout(tarjeta)
        ft.setContentsMargins(10, 10, 10, 10)
        ft.setSpacing(10)
        self.avatar_lateral = QLabel("?")
        self.avatar_lateral.setObjectName("avatar")
        self.avatar_lateral.setFixedSize(34, 34)
        self.avatar_lateral.setAlignment(Qt.AlignCenter)
        datos = QVBoxLayout()
        datos.setSpacing(0)
        self.nombre_lateral = EtiquetaElidida("")
        self.nombre_lateral.setStyleSheet("font-weight: 600; color: #FFFFFF;")
        self.correo_lateral = EtiquetaElidida("", "lateralDato")
        datos.addWidget(self.nombre_lateral)
        datos.addWidget(self.correo_lateral)
        ft.addWidget(self.avatar_lateral)
        ft.addLayout(datos, 1)
        envoltura = QHBoxLayout()
        envoltura.setContentsMargins(12, 0, 12, 6)
        envoltura.addWidget(tarjeta)
        col.addLayout(envoltura)
        salir = QPushButton(qta.icon("fa6s.right-from-bracket", color=COLOR_LATERAL), "   Cerrar sesión")
        salir.setObjectName("navBoton")
        salir.setIconSize(QSize(tema.ICONO_MENU, tema.ICONO_MENU))
        salir.setCursor(Qt.PointingHandCursor)
        salir.clicked.connect(self.cerrar_sesion)
        col.addWidget(salir)
        return lateral

    def _crear_app(self) -> QWidget:
        from app.ventanas.actividad import VentanaActividad
        from app.ventanas.generar import VentanaGenerar
        from app.ventanas.informe import VentanaInforme
        from app.ventanas.inicio import VentanaInicio
        from app.ventanas.perfil import VentanaPerfil
        from app.ventanas.planes import VentanaPlanes

        pagina = QWidget()
        fila = QHBoxLayout(pagina)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(0)

        derecha = QWidget()
        cd = QVBoxLayout(derecha)
        cd.setContentsMargins(0, 0, 0, 0)
        cd.setSpacing(0)
        superior = QFrame()
        superior.setObjectName("barraSuperior")
        superior.setFixedHeight(60)
        fs = QHBoxLayout(superior)
        fs.setContentsMargins(28, 8, 24, 8)
        fs.setSpacing(8)
        migas = QLabel("Portal del Trabajador  /")
        migas.setProperty("rol", "migas")
        self.miga_actual = QLabel("Inicio")
        self.miga_actual.setProperty("rol", "migasActual")
        self.medidor = MedidorCupo()
        self.medidor.setCursor(Qt.PointingHandCursor)
        self.medidor.mousePressEvent = lambda _e: self.ir("planes")
        self.avatar = QLabel("?")
        self.avatar.setObjectName("avatar")
        self.avatar.setFixedSize(34, 34)
        self.avatar.setAlignment(Qt.AlignCenter)
        self.avatar.setCursor(Qt.PointingHandCursor)
        self.avatar.mousePressEvent = lambda _e: self.ir("perfil")
        fs.addWidget(migas)
        fs.addWidget(self.miga_actual)
        fs.addStretch(1)
        fs.addWidget(self.medidor)
        fs.addSpacing(8)
        fs.addWidget(self.avatar)
        cd.addWidget(superior)

        self.paginas = QStackedWidget()
        self.paginas.setObjectName("paginas")
        self.secciones = {
            "inicio": VentanaInicio(self), "actividad": VentanaActividad(self), "informe": VentanaInforme(self),
            "generar": VentanaGenerar(self), "planes": VentanaPlanes(self), "perfil": VentanaPerfil(self),
        }
        for w in self.secciones.values():
            self.paginas.addWidget(w)
        cd.addWidget(self.paginas, 1)

        fila.addWidget(self._crear_lateral())
        fila.addWidget(derecha, 1)
        return pagina

    def _pintar_usuario(self) -> None:
        p = self.e.perfil or {}
        correo = p.get("email") or (self.e.sesion.email if self.e.sesion else "")
        nombre = (p.get("nombre_completo") or "").title() or correo
        letras = iniciales(p.get("nombre_completo") or "", correo)
        for a in (self.avatar, self.avatar_lateral):
            a.setText(letras)
            a.setToolTip(nombre)
            a.setAccessibleName(f"Usuario: {nombre}")
        self.nombre_lateral.poner(nombre)
        self.correo_lateral.poner(correo)

    # -------------------------------------------------------- navegación
    def ir(self, clave: str, **datos) -> None:
        """Muestra una sección de la barra lateral."""
        self.pila.setCurrentWidget(self.pag_app)
        self.botones_nav[clave].setChecked(True)
        self.miga_actual.setText(dict((c, t) for c, t, _ in SECCIONES)[clave])
        pagina = self.secciones[clave]
        self.paginas.setCurrentWidget(pagina)
        if hasattr(pagina, "al_mostrar"):
            pagina.al_mostrar(**datos)

    def _atajo(self, clave: str) -> None:
        if self.pila.currentWidget() is self.pag_app:
            self.ir(clave)

    def mostrar_login(self, mensaje: str | None = None, nivel: str = "info") -> None:
        self.pag_login.reiniciar(mensaje, nivel)
        self.pila.setCurrentWidget(self.pag_login)

    def mostrar_minuta(self, reemplazo: bool = False) -> None:
        self.pag_minuta.preparar(reemplazo)
        self.pila.setCurrentWidget(self.pag_minuta)

    def mostrar_revisar(self, lectura: dict | None = None, editar: bool = False, reemplazo: bool = False) -> None:
        self.pag_revisar.preparar(lectura=lectura, editar=editar, reemplazo=reemplazo)
        self.pila.setCurrentWidget(self.pag_revisar)

    # ---------------------------------------------------------- sesión
    def arrancar(self) -> None:
        self.pila.setCurrentWidget(self.pag_cargando)
        if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
            self.mostrar_login("Falta configurar SUPABASE_URL y SUPABASE_ANON_KEY en el archivo .env del programa.",
                               "error")
            return
        problema = config.problema_de_configuracion()
        if problema:
            self.mostrar_login(problema, "error")
            return
        self.pag_cargando.indicador.mostrar(
            "Encendiendo el programa…" if config.MODO_BACKEND == "integrado"
            else "Conectando con el servidor… Si estuvo inactivo, puede tardar hasta un minuto.")
        ejecutar(self._restaurar, al_ok=self._despues_de_restaurar, al_error=self._error_al_arrancar, contexto=self)

    def _restaurar(self):
        if config.MODO_BACKEND == "integrado":
            from app.servicios.servidor_local import servidor
            # Siempre el servidor interno (con el código de esta versión); si el puerto está ocupado, usa otro
            self.e.api.cambiar_base(servidor().asegurar(reutilizar=False))
        self._revisar_version(self._salud(self.e.api))
        if not self.e.gestor.restaurar():
            return None
        return self._cargar_usuario()

    @staticmethod
    def _salud(api) -> dict:
        """Pregunta si el servidor está listo. Con el servidor en la nube se insiste un rato antes de dar error."""
        fin = time.monotonic() + (ESPERA_SERVIDOR if config.MODO_BACKEND == "remoto" else 0)
        while True:
            try:
                return api.health()
            except ErrorApp as err:
                pasajero = err.codigo in ("sin_conexion", "tiempo_agotado") or err.status in (502, 503, 504)
                if not pasajero or time.monotonic() >= fin:
                    raise
                time.sleep(3)

    @staticmethod
    def _revisar_version(salud: dict) -> None:
        """Si el servidor exige una versión más nueva del programa, se avisa con el enlace de descarga."""
        escritorio = salud.get("escritorio") or {}
        minima = escritorio.get("version_minima") or "0"
        if config.version_tupla(config.VERSION) < config.version_tupla(minima):
            enlace = escritorio.get("url_descarga") or ""
            raise ErrorApp(f"Hay una versión nueva del programa ({minima}) y la tuya ({config.VERSION}) ya no funciona "
                           "con el servidor. Descárgala e instálala" + (f": {enlace}" if enlace else "."),
                           "version_antigua")

    def _error_al_arrancar(self, err) -> None:
        if self.pila.currentWidget() is not self.pag_cargando:
            return
        if isinstance(err, ErrorApp) and err.codigo in ("sin_backend", "sin_conexion", "version_antigua",
                                                         "tiempo_agotado"):
            self.mostrar_login(str(err), "error")
        else:
            self.mostrar_login()

    def _despues_de_restaurar(self, datos) -> None:
        if self.pila.currentWidget() is not self.pag_cargando:
            return  # el usuario ya avanzó (por ejemplo, inició sesión): no se le cambia la pantalla
        if datos is None:
            self.mostrar_login()
        else:
            self.entrar(datos)

    def _cargar_usuario(self) -> dict:
        """En segundo plano: perfil, contrato y plan."""
        perfil = self.e.cargar_perfil()
        contrato = self.e.api.contrato_actual()
        try:
            suscripcion = self.e.api.suscripcion()
        except ErrorApp:
            suscripcion = None
        return {"perfil": perfil, "contrato": contrato, "suscripcion": suscripcion}

    def iniciar_con(self, sesion) -> None:
        """Después de iniciar sesión o registrarse."""
        self.e.iniciar_sesion(sesion)
        self.pila.setCurrentWidget(self.pag_cargando)
        ejecutar(self._cargar_usuario, al_ok=self.entrar, al_error=self._error_al_entrar, contexto=self)

    def _error_al_entrar(self, err) -> None:
        self.mostrar_login(str(err), "error")

    def entrar(self, datos: dict) -> None:
        self.e.perfil = datos.get("perfil") or {}
        self.e.perfil_cambiado.emit()
        self.e.poner_contrato(datos.get("contrato") or {})
        self.e.poner_suscripcion(datos.get("suscripcion"))
        if self.e.contrato:
            self.ir("inicio")
        else:
            self.mostrar_minuta()

    def recargar_contrato(self, despues=None) -> None:
        def listo(d):
            self.e.poner_contrato(d)
            if despues:
                despues()
        ejecutar(self.e.api.contrato_actual, al_ok=listo, al_error=self.manejar_error, contexto=self)

    def recargar_suscripcion(self) -> None:
        ejecutar(self.e.api.suscripcion, al_ok=self.e.poner_suscripcion, al_error=lambda _: None, contexto=self)

    def cerrar_sesion(self, preguntar: bool = True) -> None:
        if preguntar and not dialogos.confirmar(self, "Cerrar sesión", "¿Quieres cerrar tu sesión en este equipo?",
                                                "Cerrar sesión"):
            return
        ejecutar(self.e.cerrar_sesion, al_final=lambda: self.mostrar_login("Cerraste tu sesión."), contexto=self)

    def manejar_error(self, err, aviso=None) -> None:
        """Muestra el error donde corresponde. Si la sesión terminó, vuelve al inicio de sesión."""
        if isinstance(err, ErrorApp) and (err.codigo in SESION_TERMINADA or err.status == 401):
            self.e.gestor.establecer(None)
            self.mostrar_login("Tu sesión terminó. Vuelve a iniciar sesión.", "advertencia")
            return
        texto = str(err) if isinstance(err, ErrorApp) else "Ocurrió un error inesperado. Intenta de nuevo."
        if not isinstance(err, ErrorApp):
            log.exception("Error inesperado", exc_info=err)
        if aviso is not None:
            aviso.mostrar(texto, "error")
        else:
            dialogos.error(self, "No se pudo completar", texto)
