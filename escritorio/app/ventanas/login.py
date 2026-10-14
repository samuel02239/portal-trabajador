"""Inicio de sesión / Registro / Recuperación de contraseña."""
from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from app import textos
from app.estado import estado
from app.servicios.hilos import ejecutar
from app.widgets import boton
from app.widgets.aviso import Aviso
from app.widgets.campos import CampoTexto
from app.widgets.carga import Indicador
from app.widgets.tarjeta import PaginaDividida, PanelMarca

CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
MIN_CLAVE = 8


def mostrar_aviso_datos(padre) -> None:
    caja = QMessageBox(padre)
    caja.setWindowTitle("Tratamiento de datos personales")
    caja.setTextFormat(Qt.RichText)
    caja.setText(textos.AVISO_DATOS)
    caja.exec()


def panel_marca() -> PanelMarca:
    return PanelMarca(
        "Tu informe de actividades, mes a mes.",
        "Escribe lo que hiciste con tus palabras y entrega el informe oficial listo para firmar.",
        [("fa6s.comment-dots", "Registra cada actividad en una frase, el mismo día."),
         ("fa6s.list-check", "La IA la ubica en la obligación de tu contrato y la redacta en tono formal."),
         ("fa6s.file-circle-check", "Descarga el informe en la plantilla oficial, en Word y PDF.")],
        "Tus datos se tratan conforme a la Ley 1581 de 2012.")


class VentanaLogin(PaginaDividida):
    def __init__(self, ventana):
        super().__init__(panel_marca(), 420)
        self.ventana = ventana
        self.e = estado()
        c = self.capa
        c.setSpacing(14)

        self.titulo = QLabel("Te damos la bienvenida")
        self.titulo.setProperty("rol", "titulo")
        self.subtitulo = QLabel("Inicia sesión para continuar con tu informe.")
        self.subtitulo.setProperty("rol", "secundario")
        self.subtitulo.setWordWrap(True)
        c.addWidget(self.titulo)
        c.addWidget(self.subtitulo)
        c.addSpacing(4)

        segmentos = QHBoxLayout()
        segmentos.setSpacing(0)
        self.b_entrar = QPushButton("Iniciar sesión")
        self.b_crear = QPushButton("Crear cuenta")
        self.grupo = QButtonGroup(self)
        for i, b in enumerate((self.b_entrar, self.b_crear)):
            b.setCheckable(True)
            b.setProperty("segmento", "true")
            self.grupo.addButton(b, i)
            segmentos.addWidget(b, 1)
        self.b_entrar.setChecked(True)
        self.grupo.idClicked.connect(self._cambiar_modo)
        c.addLayout(segmentos)

        self.aviso = Aviso()
        c.addWidget(self.aviso)
        self.nombre = CampoTexto("Nombre completo", "Como aparece en tu contrato")
        self.correo = CampoTexto("Correo", "tucorreo@ejemplo.com")
        self.clave = CampoTexto("Contraseña", clave=True)
        for w in (self.nombre, self.correo, self.clave):
            c.addWidget(w)
            w.campo.returnPressed.connect(self._enviar)

        fila_datos = QHBoxLayout()
        self.acepto = QCheckBox("Acepto el tratamiento de mis datos")
        self.acepto.setAccessibleName("Acepto el tratamiento de mis datos personales (Ley 1581 de 2012)")
        leer = boton("Leer aviso", "enlace")
        leer.clicked.connect(lambda: mostrar_aviso_datos(self))
        fila_datos.addWidget(self.acepto, 1)
        fila_datos.addWidget(leer)
        self.contenedor_datos = QWidget()
        self.contenedor_datos.setLayout(fila_datos)
        fila_datos.setContentsMargins(0, 0, 0, 0)
        c.addWidget(self.contenedor_datos)

        self.indicador = Indicador()
        c.addWidget(self.indicador)
        self.enviar = boton("Entrar", "primario")
        self.enviar.clicked.connect(self._enviar)
        c.addWidget(self.enviar)
        self.olvido = boton("¿Olvidaste tu contraseña?", "enlace")
        self.olvido.clicked.connect(self._recuperar)
        c.addWidget(self.olvido, 0, Qt.AlignLeft)
        self._cambiar_modo(0)

    # ------------------------------------------------------------------
    def reiniciar(self, mensaje: str | None = None, nivel: str = "info") -> None:
        self.clave.poner("")
        self.indicador.ocultar()
        self._ocupado(False)
        if mensaje:
            self.aviso.mostrar(mensaje, nivel)
        else:
            self.aviso.ocultar()

    @property
    def creando(self) -> bool:
        return self.grupo.checkedId() == 1

    def _cambiar_modo(self, modo: int) -> None:
        crear = modo == 1
        self.titulo.setText("Crea tu cuenta" if crear else "Te damos la bienvenida")
        self.subtitulo.setText("Empiezas con 1 informe gratis." if crear
                               else "Inicia sesión para continuar con tu informe.")
        self.nombre.setVisible(crear)
        self.contenedor_datos.setVisible(crear)
        self.olvido.setVisible(not crear)
        self.enviar.setText("Crear cuenta" if crear else "Entrar")
        self.clave.etiqueta.setText(f"Contraseña (mínimo {MIN_CLAVE} caracteres)" if crear else "Contraseña")
        self.aviso.ocultar()
        for w in (self.nombre, self.correo, self.clave):
            w.error(None)
        (self.nombre if crear else self.correo).campo.setFocus()

    def _ocupado(self, si: bool) -> None:
        for w in (self.enviar, self.b_entrar, self.b_crear, self.olvido):
            w.setEnabled(not si)

    def _validar(self) -> bool:
        ok = True
        if self.creando and len(self.nombre.texto()) < 5:
            self.nombre.error("Escribe tu nombre completo.")
            ok = False
        if not CORREO.match(self.correo.texto()):
            self.correo.error("Escribe un correo válido.")
            ok = False
        if self.creando and len(self.clave.campo.text()) < MIN_CLAVE:
            self.clave.error(f"La contraseña debe tener al menos {MIN_CLAVE} caracteres.")
            ok = False
        elif not self.clave.campo.text():
            self.clave.error("Escribe tu contraseña.")
            ok = False
        if self.creando and not self.acepto.isChecked():
            self.aviso.mostrar("Para crear la cuenta debes aceptar el tratamiento de tus datos personales.",
                               "advertencia")
            ok = False
        return ok

    def _enviar(self) -> None:
        if not self.enviar.isEnabled() or not self._validar():
            return
        self.aviso.ocultar()
        self._ocupado(True)
        correo, clave = self.correo.texto().lower(), self.clave.campo.text()
        if self.creando:
            self.indicador.mostrar("Creando tu cuenta…")
            ejecutar(self.e.auth.registrar, correo, clave, self.nombre.texto(), al_ok=self._registrado,
                     al_error=self._error, contexto=self)
        else:
            self.indicador.mostrar("Entrando…")
            ejecutar(self.e.auth.iniciar, correo, clave, al_ok=self.ventana.iniciar_con, al_error=self._error,
                     contexto=self)

    def _registrado(self, sesion) -> None:
        self.indicador.ocultar()
        self._ocupado(False)
        if sesion:
            self.ventana.iniciar_con(sesion)
            return
        self.b_entrar.setChecked(True)
        self._cambiar_modo(0)
        self.aviso.mostrar("Cuenta creada. Te enviamos un correo para confirmarla: abre el enlace y luego "
                           "inicia sesión aquí.", "exito")
        self.clave.campo.setFocus()

    def _error(self, err) -> None:
        self.indicador.ocultar()
        self._ocupado(False)
        self.aviso.mostrar(str(err), "error")

    def _recuperar(self) -> None:
        dlg = DialogoRecuperar(self, self.correo.texto())
        if dlg.exec() == QDialog.Accepted and dlg.sesion:
            self.ventana.iniciar_con(dlg.sesion)


class DialogoRecuperar(QDialog):
    """Recuperación con código del correo (Supabase envía el código con la plantilla de correo configurada)."""

    def __init__(self, padre, correo: str = ""):
        super().__init__(padre)
        self.setWindowTitle("Recuperar contraseña")
        self.setMinimumWidth(440)
        self.e = estado()
        self.sesion = None
        capa = QVBoxLayout(self)
        self.pasos = QStackedWidget()
        capa.addWidget(self.pasos)
        self.aviso = Aviso()
        capa.addWidget(self.aviso)
        self.indicador = Indicador()
        capa.addWidget(self.indicador)

        p1 = QWidget()
        c1 = QVBoxLayout(p1)
        ayuda = QLabel(textos.AYUDA_RECUPERAR)
        ayuda.setWordWrap(True)
        self.correo = CampoTexto("Correo de tu cuenta")
        self.correo.poner(correo)
        c1.addWidget(ayuda)
        c1.addWidget(self.correo)
        self.pasos.addWidget(p1)

        p2 = QWidget()
        c2 = QVBoxLayout(p2)
        self.codigo = CampoTexto("Código que llegó a tu correo")
        self.nueva = CampoTexto(f"Nueva contraseña (mínimo {MIN_CLAVE} caracteres)", clave=True)
        self.repetir = CampoTexto("Repite la nueva contraseña", clave=True)
        for w in (self.codigo, self.nueva, self.repetir):
            c2.addWidget(w)
        self.pasos.addWidget(p2)

        self.botones = QDialogButtonBox()
        self.continuar = self.botones.addButton("Enviar código", QDialogButtonBox.AcceptRole)
        self.continuar.setProperty("variante", "primario")
        self.botones.addButton("Cancelar", QDialogButtonBox.RejectRole)
        self.botones.accepted.connect(self._siguiente)
        self.botones.rejected.connect(self.reject)
        capa.addWidget(self.botones)

    def _ocupado(self, si: bool, texto: str = "") -> None:
        self.continuar.setEnabled(not si)
        self.indicador.mostrar(texto) if si else self.indicador.ocultar()

    def _siguiente(self) -> None:
        self.aviso.ocultar()
        if self.pasos.currentIndex() == 0:
            correo = self.correo.texto().lower()
            if not CORREO.match(correo):
                self.correo.error("Escribe un correo válido.")
                return
            self._ocupado(True, "Enviando…")
            ejecutar(self.e.auth.recuperar, correo, al_ok=self._enviado, al_error=self._error, contexto=self)
            return
        codigo = re.sub(r"\D", "", self.codigo.texto())
        if len(codigo) < 6:
            self.codigo.error("Escribe el código de 6 dígitos que llegó a tu correo.")
            return
        if len(self.nueva.campo.text()) < MIN_CLAVE:
            self.nueva.error(f"Usa al menos {MIN_CLAVE} caracteres.")
            return
        if self.nueva.campo.text() != self.repetir.campo.text():
            self.repetir.error("Las contraseñas no coinciden.")
            return
        self._ocupado(True, "Cambiando la contraseña…")
        correo, nueva = self.correo.texto().lower(), self.nueva.campo.text()

        def cambiar():
            sesion = self.e.auth.verificar_recuperacion(correo, codigo)
            self.e.auth.cambiar_password(sesion.access_token, nueva)
            return sesion

        ejecutar(cambiar, al_ok=self._listo, al_error=self._error, contexto=self)

    def _enviado(self, _) -> None:
        self._ocupado(False)
        self.pasos.setCurrentIndex(1)
        self.continuar.setText("Cambiar contraseña")
        self.aviso.mostrar("Si el correo tiene una cuenta, te llegará un código en unos minutos.", "info")
        self.codigo.campo.setFocus()

    def _listo(self, sesion) -> None:
        self._ocupado(False)
        self.sesion = sesion
        self.accept()

    def _error(self, err) -> None:
        self._ocupado(False)
        self.aviso.mostrar(str(err), "error")
