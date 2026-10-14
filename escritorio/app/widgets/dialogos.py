"""Diálogos de confirmación y mensajes."""
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox


def confirmar(padre, titulo: str, texto: str, aceptar: str = "Sí, continuar", peligro: bool = False) -> bool:
    caja = QMessageBox(padre)
    caja.setWindowTitle(titulo)
    caja.setText(texto)
    caja.setIcon(QMessageBox.Warning if peligro else QMessageBox.Question)
    si = caja.addButton(aceptar, QMessageBox.AcceptRole)
    no = caja.addButton("Cancelar", QMessageBox.RejectRole)
    si.setProperty("variante", "peligro" if peligro else "primario")
    caja.setDefaultButton(no if peligro else si)
    caja.exec()
    return caja.clickedButton() is si


def informar(padre, titulo: str, texto: str) -> None:
    QMessageBox.information(padre, titulo, texto)


def error(padre, titulo: str, texto: str) -> None:
    QMessageBox.warning(padre, titulo, texto)


def pedir_texto(padre, titulo: str, etiqueta: str, clave: bool = False) -> str | None:
    texto, ok = QInputDialog.getText(padre, titulo, etiqueta, QLineEdit.Password if clave else QLineEdit.Normal)
    return texto.strip() if ok else None
