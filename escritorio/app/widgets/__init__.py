"""Componentes visuales reutilizables (sección 9.3)."""
from PySide6.QtWidgets import QPushButton

# Gris neutro con contraste ≥ 3:1 tanto en el tema claro como en el oscuro (íconos de acciones)
COLOR_ICONO = "#6E8085"


def icono(nombre: str, color: str = COLOR_ICONO):
    import qtawesome as qta
    return qta.icon(nombre, color=color)


def mostrar_en(capa, widget, *args):
    """Agrega un widget a una capa ya visible y lo muestra de inmediato.

    Sin el show() explícito Qt lo muestra en un evento posterior y, mientras tanto,
    la capa calcula los tamaños sin él (las secciones se ven aplastadas un momento).
    """
    capa.addWidget(widget, *args)
    widget.show()
    return widget


def plural(n: int, singular: str, plural_: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural_ or singular + 's')}"


def boton(texto: str, variante: str = "secundario", icono=None, atajo: str | None = None) -> QPushButton:
    """Botón primario / secundario / peligro / enlace."""
    b = QPushButton(texto)
    b.setProperty("variante", variante)
    if icono is not None:
        b.setIcon(icono)
    if atajo:
        b.setShortcut(atajo)
        b.setToolTip(f"{texto} ({atajo})")
    return b


def refrescar_estilo(widget) -> None:
    """Vuelve a aplicar el QSS después de cambiar una propiedad dinámica."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
