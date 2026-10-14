"""Campos con etiqueta y mensaje de error; área de texto con contador; campo de fecha opcional."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import QComboBox, QDateEdit, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from app.widgets import refrescar_estilo


class _ConEtiqueta(QWidget):
    def __init__(self, etiqueta: str, campo: QWidget, ayuda: str | None = None, parent=None):
        super().__init__(parent)
        self.campo = campo
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(4)
        self.etiqueta = QLabel(etiqueta)
        self.etiqueta.setBuddy(campo)
        self.etiqueta.setWordWrap(True)
        capa.addWidget(self.etiqueta)
        capa.addWidget(campo)
        if ayuda:
            a = QLabel(ayuda)
            a.setProperty("rol", "secundario")
            a.setWordWrap(True)
            capa.addWidget(a)
        self.mensaje = QLabel()
        self.mensaje.setProperty("rol", "error")
        self.mensaje.setWordWrap(True)
        self.mensaje.hide()
        capa.addWidget(self.mensaje)
        campo.setAccessibleName(etiqueta.replace("&", ""))

    def error(self, texto: str | None) -> None:
        self.campo.setProperty("error", bool(texto))
        refrescar_estilo(self.campo)
        self.mensaje.setText(texto or "")
        self.mensaje.setVisible(bool(texto))
        if texto:
            self.campo.setAccessibleDescription(texto)


class CampoTexto(_ConEtiqueta):
    def __init__(self, etiqueta: str, placeholder: str = "", clave: bool = False, ayuda: str | None = None,
                 parent=None):
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        if clave:
            edit.setEchoMode(QLineEdit.Password)
        super().__init__(etiqueta, edit, ayuda, parent)
        edit.textEdited.connect(lambda _: self.error(None))

    def texto(self) -> str:
        return self.campo.text().strip()

    def poner(self, valor) -> None:
        self.campo.setText("" if valor is None else str(valor))
        self.campo.setCursorPosition(0)  # muestra el comienzo de los textos largos


class AreaTexto(_ConEtiqueta):
    """Área de texto con contador de caracteres."""
    cambio = Signal()

    def __init__(self, etiqueta: str, placeholder: str = "", maximo: int = 2000, alto: int = 110,
                 ayuda: str | None = None, parent=None):
        edit = QPlainTextEdit()
        edit.setPlaceholderText(placeholder)
        edit.setMinimumHeight(alto)
        edit.setTabChangesFocus(True)
        super().__init__(etiqueta, edit, ayuda, parent)
        self.maximo = maximo
        self.contador = QLabel()
        self.contador.setProperty("rol", "secundario")
        fila = QHBoxLayout()
        fila.addStretch(1)
        fila.addWidget(self.contador)
        self.layout().insertLayout(2, fila)
        edit.textChanged.connect(self._contar)
        self._contar()

    def _contar(self) -> None:
        n = len(self.campo.toPlainText())
        if n > self.maximo:
            cursor = self.campo.textCursor()
            self.campo.setPlainText(self.campo.toPlainText()[:self.maximo])
            cursor.setPosition(self.maximo)
            self.campo.setTextCursor(cursor)
            n = self.maximo
        self.contador.setText(f"{n} / {self.maximo}")
        self.error(None)
        self.cambio.emit()

    def texto(self) -> str:
        return self.campo.toPlainText().strip()

    def poner(self, valor) -> None:
        self.campo.setPlainText("" if valor is None else str(valor))


class CampoFecha(_ConEtiqueta):
    """Fecha que puede quedar vacía ('Sin fecha')."""
    MINIMA = QDate(2000, 1, 1)

    def __init__(self, etiqueta: str, opcional: bool = True, ayuda: str | None = None, parent=None):
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("dd/MM/yyyy")
        if opcional:
            edit.setMinimumDate(self.MINIMA)
            edit.setSpecialValueText("Sin fecha")
            edit.setDate(self.MINIMA)
        else:
            edit.setDate(QDate.currentDate())
        super().__init__(etiqueta, edit, ayuda, parent)
        self.opcional = opcional
        edit.dateChanged.connect(lambda _: self.error(None))

    def fecha(self) -> date | None:
        d = self.campo.date()
        if self.opcional and d == self.MINIMA:
            return None
        return date(d.year(), d.month(), d.day())

    def iso(self) -> str | None:
        f = self.fecha()
        return f.isoformat() if f else None

    def poner(self, valor) -> None:
        if not valor:
            self.campo.setDate(self.MINIMA if self.opcional else QDate.currentDate())
            return
        if isinstance(valor, str):
            valor = date.fromisoformat(valor[:10])
        self.campo.setDate(QDate(valor.year, valor.month, valor.day))


class CampoOpciones(_ConEtiqueta):
    def __init__(self, etiqueta: str, opciones: list[tuple[str, object]], ayuda: str | None = None, parent=None):
        combo = QComboBox()
        for texto, valor in opciones:
            combo.addItem(texto, valor)
        super().__init__(etiqueta, combo, ayuda, parent)

    def valor(self):
        return self.campo.currentData()

    def poner(self, valor) -> None:
        i = self.campo.findData(valor)
        if i >= 0:
            self.campo.setCurrentIndex(i)
