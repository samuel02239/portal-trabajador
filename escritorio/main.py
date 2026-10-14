"""Portal del Trabajador · programa de escritorio (PySide6).

Correr en desarrollo:  python main.py
"""
import logging
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from app import config, tema


def configurar_log() -> None:
    config.CARPETA_LOGS.mkdir(parents=True, exist_ok=True)
    manejador = RotatingFileHandler(config.CARPETA_LOGS / "portal.log", maxBytes=1_000_000, backupCount=3,
                                    encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[manejador],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def cargar_fuentes() -> None:
    carpeta = config.RECURSOS / "fuentes"
    if carpeta.exists():
        for archivo in carpeta.glob("*.[ot]tf"):
            QFontDatabase.addApplicationFont(str(archivo))


def main() -> int:
    configurar_log()
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NOMBRE)
    app.setOrganizationName(config.APP_ORG)
    app.setApplicationVersion(config.VERSION)
    icono = config.RECURSOS / "icono.png"
    if icono.exists():
        app.setWindowIcon(QIcon(str(icono)))
    cargar_fuentes()

    from app.estado import estado
    e = estado()
    tema.aplicar(app, e.modo_tema())
    try:  # si Windows cambia entre claro y oscuro, el programa lo sigue (cuando el modo es "sistema")
        app.styleHints().colorSchemeChanged.connect(
            lambda _: tema.aplicar(app, e.modo_tema()) if e.modo_tema() == "sistema" else None)
    except AttributeError:
        pass

    if config.MODO_BACKEND == "integrado":  # al cerrar el programa se apaga su servidor interno
        from app.servicios.servidor_local import servidor
        app.aboutToQuit.connect(servidor().detener)

    from app.ventanas.principal import VentanaPrincipal
    if "--verificar" in sys.argv:
        return verificar(app, VentanaPrincipal)
    ventana = VentanaPrincipal()
    ventana.resize(1280, 800)
    ventana.show()
    return app.exec()


def verificar(app, VentanaPrincipal) -> int:
    """Prueba de humo del ejecutable: arma todas las pantallas sin mostrarlas y revisa los recursos."""
    faltan = [n for n in ("icono.png", "icono.ico", "fuentes") if not (config.RECURSOS / n).exists()]
    import keyring
    almacen = type(keyring.get_keyring()).__name__
    if "fail" in almacen.lower() or "null" in almacen.lower():
        faltan.append(f"keyring ({almacen})")
    try:
        v = VentanaPrincipal()
        v.setAttribute(Qt.WA_DontShowOnScreen)
        v.show()
        app.processEvents()
        v.close()
    except Exception:
        logging.exception("Verificación: no se pudo armar la ventana")
        return 2
    logging.info("Verificación %s; faltantes: %s; credenciales: %s; servidor: %s", "OK" if not faltan else "INCOMPLETA",
                 faltan, almacen, config.API_BASE_URL)
    return 0 if not faltan else 3


if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    sys.exit(main())
