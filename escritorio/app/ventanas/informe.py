"""Mi informe: actividades del periodo agrupadas por obligación (acordeón), editables y movibles."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
                               QLabel, QListWidget, QListWidgetItem, QMenu, QPushButton, QVBoxLayout)

from app import config
from app.estado import estado
from app.servicios import archivos_locales
from app.servicios.hilos import ejecutar
from app.ventanas.actividad import EXTENSIONES_EVIDENCIA, titulo_obligacion
from app.widgets import boton, dialogos, icono, plural, mostrar_en
from app.widgets.aviso import Aviso
from app.widgets.campos import AreaTexto, CampoFecha
from app.widgets.carga import Indicador
from app.widgets.insignia import Insignia
from app.widgets.plegable import SeccionPlegable
from app.widgets.tarjeta import PaginaDesplazable


def fecha_corta(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return d.strftime("%d/%m/%Y")


class SelectorPeriodo(QComboBox):
    """Combo de periodos (YYYY-MM) compartido entre Mi informe y Generar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Periodo del informe")
        self.setMinimumWidth(180)

    def poner(self, periodos: list[dict], actual: str) -> None:
        self.blockSignals(True)
        self.clear()
        for p in periodos:
            self.addItem(p["etiqueta"], p["clave"])
        i = self.findData(actual)
        self.setCurrentIndex(i if i >= 0 else self.count() - 1)
        self.blockSignals(False)


def alertas_resumidas(alertas: list[dict]) -> list[tuple[str, str]]:
    """Agrupa las alertas de 'obligación sin actividades' en un solo aviso."""
    sin = [a for a in alertas if a["codigo"] == "obligacion_sin_actividades"]
    otras = [a for a in alertas if a["codigo"] != "obligacion_sin_actividades"]
    salida = [(a["mensaje"], a["nivel"]) for a in otras]
    if sin:
        numeros = ", ".join(a["mensaje"].split()[2] for a in sin)
        salida.append((f"Obligaciones sin actividades en este periodo: {numeros}.", "advertencia"))
    orden = {"error": 0, "advertencia": 1, "info": 2}
    return sorted(salida, key=lambda x: orden.get(x[1], 3))


class DialogoActividad(QDialog):
    """Editar fecha, obligación, redacción y evidencias de una actividad."""

    def __init__(self, padre, actividad: dict, obligaciones: list[dict]):
        super().__init__(padre)
        self.setWindowTitle("Editar actividad")
        self.setMinimumWidth(560)
        self.e = estado()
        self.actividad = actividad
        self.cambios_evidencia = False
        c = QVBoxLayout(self)
        original = QLabel(f"Lo que escribiste: “{actividad['texto_original']}”")
        original.setProperty("rol", "cita")
        original.setWordWrap(True)
        c.addWidget(original)
        self.fecha = CampoFecha("Fecha", opcional=False)
        self.fecha.poner(actividad["fecha"])
        self.fecha.setMaximumWidth(220)
        c.addWidget(self.fecha)
        etiqueta = QLabel("Obligación")
        self.combo = QComboBox()
        etiqueta.setBuddy(self.combo)
        for o in obligaciones:
            self.combo.addItem(titulo_obligacion(o), o["id"])
            self.combo.setItemData(self.combo.count() - 1, o["texto"], Qt.ToolTipRole)
        self.combo.addItem("Sin obligación (no sale en el informe)", None)
        i = self.combo.findData(actividad.get("obligacion_id"))
        self.combo.setCurrentIndex(i if i >= 0 else self.combo.count() - 1)
        c.addWidget(etiqueta)
        c.addWidget(self.combo)
        self.redaccion = AreaTexto("Redacción en el informe", maximo=6000, alto=120)
        self.redaccion.poner(actividad.get("texto_redactado") or actividad["texto_original"])
        c.addWidget(self.redaccion)

        ev = QLabel("Evidencias (anexos)")
        ev.setProperty("rol", "seccion")
        c.addWidget(ev)
        ayuda = QLabel("Este es el texto con el que cada anexo aparece en el informe. Doble clic para editarlo.")
        ayuda.setProperty("rol", "secundario")
        ayuda.setWordWrap(True)
        c.addWidget(ayuda)
        self.lista = QListWidget()
        self.lista.setMaximumHeight(130)
        self.lista.setWordWrap(True)
        self.lista.itemDoubleClicked.connect(lambda _i: self._editar_descripcion())
        for e in actividad.get("evidencias") or []:
            self._agregar_item(e)
        c.addWidget(self.lista)
        fila = QHBoxLayout()
        agregar = boton("Agregar evidencia", "secundario", icono("fa6s.paperclip"))
        editar = boton("Editar descripción", "enlace")
        regenerar = boton("Volver a describir con IA", "enlace")
        quitar = boton("Quitar seleccionada", "enlace")
        agregar.clicked.connect(self._agregar)
        editar.clicked.connect(self._editar_descripcion)
        regenerar.clicked.connect(self._regenerar)
        quitar.clicked.connect(self._quitar)
        for b in (agregar, editar, regenerar, quitar):
            fila.addWidget(b)
        fila.addStretch(1)
        c.addLayout(fila)
        self.aviso = Aviso()
        self.indicador = Indicador()
        c.addWidget(self.aviso)
        c.addWidget(self.indicador)
        botones = QDialogButtonBox()
        self.b_guardar = botones.addButton("Guardar", QDialogButtonBox.AcceptRole)
        self.b_guardar.setProperty("variante", "primario")
        botones.addButton("Cancelar", QDialogButtonBox.RejectRole)
        botones.accepted.connect(self._guardar)
        botones.rejected.connect(self.reject)
        c.addWidget(botones)

    def _agregar_item(self, e: dict, fila: int | None = None) -> None:
        texto = f"Anexo: {e.get('descripcion') or e['nombre']}"
        item = QListWidgetItem(icono("fa6s.paperclip"), texto)
        item.setData(Qt.UserRole, e["id"])
        item.setData(Qt.UserRole + 1, e.get("descripcion") or "")
        item.setToolTip(f"Archivo: {e['nombre']}")
        if fila is None:
            self.lista.addItem(item)
        else:
            self.lista.takeItem(fila)
            self.lista.insertItem(fila, item)
            self.lista.setCurrentRow(fila)

    def _agregar(self) -> None:
        rutas, _ = QFileDialog.getOpenFileNames(self, "Agregar evidencias", "", EXTENSIONES_EVIDENCIA)
        rutas = [r for r in rutas if Path(r).stat().st_size <= config.MAX_ARCHIVO]
        if not rutas:
            return
        try:
            fecha = date.fromisoformat(self.actividad["fecha"][:10])
            copias = [str(archivos_locales.guardar_copia(r, fecha)) for r in rutas]
        except OSError as exc:
            self.aviso.mostrar(f"No se pudo guardar la copia local: {exc}", "error")
            return
        self.indicador.mostrar("Subiendo y describiendo el anexo…")
        api, aid = self.e.api, self.actividad["id"]
        ejecutar(lambda: [api.subir_evidencia(aid, r) for r in copias], al_ok=self._subidas,
                 al_error=lambda err: self.aviso.mostrar(str(err), "error"), al_final=self.indicador.ocultar,
                 contexto=self)

    def _subidas(self, evidencias: list[dict]) -> None:
        self.cambios_evidencia = True
        for e in evidencias:
            self._agregar_item(e)

    def _seleccion(self):
        items = self.lista.selectedItems()
        return (items[0], self.lista.row(items[0])) if items else (None, None)

    def _editar_descripcion(self) -> None:
        item, fila = self._seleccion()
        if not item:
            self.aviso.mostrar("Selecciona un anexo de la lista.", "info")
            return
        texto, ok = QInputDialog.getMultiLineText(self, "Descripción del anexo",
                                                  "Así aparecerá el anexo en el informe:",
                                                  item.data(Qt.UserRole + 1))
        if not ok or not texto.strip():
            return
        ejecutar(self.e.api.editar_evidencia, self.actividad["id"], item.data(Qt.UserRole), texto.strip(),
                 al_ok=lambda e: (self._agregar_item({**e}, fila), setattr(self, "cambios_evidencia", True)),
                 al_error=lambda err: self.aviso.mostrar(str(err), "error"), contexto=self)

    def _regenerar(self) -> None:
        item, fila = self._seleccion()
        if not item:
            self.aviso.mostrar("Selecciona un anexo de la lista.", "info")
            return
        self.indicador.mostrar("Describiendo el anexo con IA…")
        ejecutar(self.e.api.editar_evidencia, self.actividad["id"], item.data(Qt.UserRole), None, True,
                 al_ok=lambda e: (self._agregar_item({**e}, fila), setattr(self, "cambios_evidencia", True)),
                 al_error=lambda err: self.aviso.mostrar(str(err), "error"), al_final=self.indicador.ocultar,
                 contexto=self)

    def _quitar(self) -> None:
        items = self.lista.selectedItems()
        if not items or not dialogos.confirmar(self, "Quitar evidencia", "¿Quitar la evidencia seleccionada?",
                                               "Quitar", peligro=True):
            return
        item = items[0]
        eid = item.data(Qt.UserRole)
        ejecutar(self.e.api.borrar_evidencia, self.actividad["id"], eid,
                 al_ok=lambda _: (self.lista.takeItem(self.lista.row(item)), setattr(self, "cambios_evidencia", True)),
                 al_error=lambda err: self.aviso.mostrar(str(err), "error"), contexto=self)

    def _guardar(self) -> None:
        cambios = {}
        texto = self.redaccion.texto()
        if texto != (self.actividad.get("texto_redactado") or ""):
            cambios["texto_redactado"] = texto
        if self.combo.currentData() != self.actividad.get("obligacion_id") or \
                (self.combo.currentData() and self.actividad["estado"] != "confirmada"):
            cambios["obligacion_id"] = self.combo.currentData()
        if self.fecha.iso() != self.actividad["fecha"][:10]:
            cambios["fecha"] = self.fecha.iso()
        if not cambios:
            self.accept() if self.cambios_evidencia else self.reject()
            return
        self.b_guardar.setEnabled(False)
        self.indicador.mostrar("Guardando…")
        ejecutar(self.e.api.editar_actividad, self.actividad["id"], cambios, al_ok=lambda _: self.accept(),
                 al_error=lambda err: (self.aviso.mostrar(str(err), "error"), self.b_guardar.setEnabled(True)),
                 al_final=self.indicador.ocultar, contexto=self)


class FilaActividad(QFrame):
    def __init__(self, actividad: dict, pagina: "VentanaInforme"):
        super().__init__()
        self.actividad, self.pagina = actividad, pagina
        self.setObjectName("filaActividad")
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 10, 0, 10)
        fila.setSpacing(16)
        izq = QVBoxLayout()
        izq.setSpacing(6)
        f = QLabel(fecha_corta(actividad["fecha"]))
        f.setProperty("rol", "seccion")
        izq.addWidget(f)
        izq.addWidget(Insignia(actividad["estado"]), 0, Qt.AlignLeft)
        izq.addStretch(1)
        centro = QVBoxLayout()
        texto = QLabel(actividad.get("texto_redactado") or actividad["texto_original"])
        texto.setWordWrap(True)
        texto.setTextInteractionFlags(Qt.TextSelectableByMouse)
        centro.addWidget(texto)
        for e in actividad.get("evidencias") or []:
            ev = QLabel(f"Anexo: {e.get('descripcion') or e['nombre']}")
            ev.setProperty("rol", "secundario")
            ev.setWordWrap(True)
            ev.setToolTip(f"Archivo: {e['nombre']}")
            centro.addWidget(ev)
        der = QHBoxLayout()
        editar = QPushButton(icono("fa6s.pen-to-square"), "")
        editar.setToolTip("Editar")
        editar.setAccessibleName("Editar actividad")
        editar.clicked.connect(lambda: pagina.editar(actividad))
        mover = QPushButton(icono("fa6s.arrow-right-arrow-left"), "")
        mover.setToolTip("Mover a otra obligación")
        mover.setAccessibleName("Mover a otra obligación")
        mover.clicked.connect(lambda: pagina.menu_mover(actividad, mover))
        borrar = QPushButton(icono("fa6s.trash"), "")
        borrar.setToolTip("Eliminar")
        borrar.setAccessibleName("Eliminar actividad")
        borrar.clicked.connect(lambda: pagina.borrar(actividad))
        for b in (editar, mover, borrar):
            b.setProperty("variante", "icono")
            b.setCursor(Qt.PointingHandCursor)
            der.addWidget(b, 0, Qt.AlignTop)
        fila.addLayout(izq)
        fila.addLayout(centro, 1)
        fila.addLayout(der)


class VentanaInforme(PaginaDesplazable):
    def __init__(self, ventana):
        super().__init__()
        self.ventana = ventana
        self.e = estado()
        self.datos: dict | None = None
        c = self.capa
        cab = QHBoxLayout()
        titulo = QLabel("Mi informe")
        titulo.setProperty("rol", "titulo")
        self.selector = SelectorPeriodo()
        self.selector.currentIndexChanged.connect(lambda _: self._cambiar_periodo())
        generar = boton("Generar informe", "primario")
        generar.clicked.connect(lambda: self.ventana.ir("generar"))
        cab.addWidget(titulo)
        cab.addStretch(1)
        etiqueta = QLabel("Periodo")
        etiqueta.setProperty("rol", "secundario")
        etiqueta.setBuddy(self.selector)
        cab.addWidget(etiqueta)
        cab.addWidget(self.selector)
        cab.addWidget(generar)
        c.addLayout(cab)
        self.resumen = QLabel()
        self.resumen.setProperty("rol", "secundario")
        c.addWidget(self.resumen)
        self.aviso = Aviso(cerrable=True)
        c.addWidget(self.aviso)
        self.alertas = QVBoxLayout()
        c.addLayout(self.alertas)
        self.indicador = Indicador("Cargando tu informe…")
        c.addWidget(self.indicador)
        self.secciones = QVBoxLayout()
        self.secciones.setSpacing(10)
        c.addLayout(self.secciones)
        self.abiertas: set[str] = set()
        self._viejo = True
        self.e.actividades_cambiadas.connect(lambda: setattr(self, "_viejo", True))
        self.e.contrato_cambiado.connect(lambda: setattr(self, "_viejo", True))
        self.e.periodo_cambiado.connect(lambda _: setattr(self, "_viejo", True))

    def al_mostrar(self, **_) -> None:
        if self._viejo:
            self.cargar()

    def _cambiar_periodo(self) -> None:
        clave = self.selector.currentData()
        if clave:
            self.e.poner_periodo(clave)
            self.cargar()

    def cargar(self) -> None:
        self.indicador.mostrar()
        ejecutar(self.e.api.informe_actual, self.e.periodo, al_ok=self._poner,
                 al_error=lambda err: self.ventana.manejar_error(err, self.aviso), al_final=self.indicador.ocultar,
                 contexto=self)

    def _limpiar(self, capa) -> None:
        while capa.count():
            w = capa.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _poner(self, d: dict) -> None:
        self._viejo = False
        self.datos = d
        self.e.periodo = d["periodo"]["clave"]
        self.selector.poner(d["periodos"], d["periodo"]["clave"])
        k = d["conteo"]
        self.resumen.setText(f"{d['periodo']['etiqueta']} ({fecha_corta(d['periodo']['inicio'])} al "
                             f"{fecha_corta(d['periodo']['fin'])}) · {plural(k['total'], 'actividad', 'actividades')} · "
                             f"{plural(k['confirmadas'], 'confirmada')} · {k['sin_obligacion']} sin obligación")
        self._limpiar(self.alertas)
        for texto, nivel in alertas_resumidas(d["alertas"]):
            mostrar_en(self.alertas, Aviso(texto, nivel))
        self._limpiar(self.secciones)
        for o in d["obligaciones"]:
            n = len(o["actividades"])
            sec = SeccionPlegable(f"{o['numero']}. {o['titulo_corto']}", abierta=o["id"] in self.abiertas or
                                  (n > 0 and not self.abiertas))
            sec.cabecera.setToolTip(o["texto"])
            sec.cabecera.toggled.connect(lambda si, oid=o["id"]: self.abiertas.add(oid) if si else self.abiertas.discard(oid))
            sec.agregar_a_cabecera(Insignia("neutra", plural(n, "actividad", "actividades")) if n
                                   else Insignia("media", "⚠ Sin actividades"))
            completo = QLabel(o["texto"])
            completo.setProperty("rol", "secundario")
            completo.setWordWrap(True)
            sec.capa.addWidget(completo)
            if not n:
                vacio = QLabel("Todavía no hay actividades en esta obligación para este periodo.")
                vacio.setProperty("rol", "secundario")
                sec.capa.addWidget(vacio)
            for a in o["actividades"]:
                sec.capa.addWidget(FilaActividad(a, self))
            mostrar_en(self.secciones, sec)
        if d["sin_obligacion"]:
            sec = SeccionPlegable("Sin obligación (no salen en el informe)", abierta=True)
            sec.agregar_a_cabecera(Insignia("sin_obligacion", str(len(d["sin_obligacion"]))))
            for a in d["sin_obligacion"]:
                sec.capa.addWidget(FilaActividad(a, self))
            mostrar_en(self.secciones, sec)
        if not k["total"]:
            vacio = Aviso("Aún no registras actividades en este periodo. Ve a Actividad (Ctrl+N) para empezar.", "info")
            vacio.accion.connect(lambda: self.ventana.ir("actividad"))
            vacio.mostrar(vacio.texto.text(), "info", accion="Registrar actividad")
            mostrar_en(self.secciones, vacio)

    # -------------------------------------------------------------- acciones
    def editar(self, actividad: dict) -> None:
        dlg = DialogoActividad(self, actividad, self.e.especificas())
        if dlg.exec() == QDialog.Accepted:
            self.aviso.mostrar("Guardamos los cambios de la actividad.", "exito")
            self.e.actividades_cambiadas.emit()
            self.cargar()

    def menu_mover(self, actividad: dict, ancla) -> None:
        menu = QMenu(self)
        for o in self.e.especificas():
            if o["id"] == actividad.get("obligacion_id") and actividad["estado"] == "confirmada":
                continue
            accion = menu.addAction(titulo_obligacion(o))
            accion.setToolTip(o["texto"])
            accion.triggered.connect(lambda _=False, oid=o["id"]: self._mover(actividad, oid))
        if actividad.get("obligacion_id"):
            menu.addSeparator()
            menu.addAction("Quitar de la obligación").triggered.connect(lambda: self._mover(actividad, None))
        menu.exec(ancla.mapToGlobal(ancla.rect().bottomLeft()))

    def _mover(self, actividad: dict, obligacion_id: str | None) -> None:
        ejecutar(self.e.api.editar_actividad, actividad["id"], {"obligacion_id": obligacion_id},
                 al_ok=lambda _: self._hecho("Movimos la actividad."),
                 al_error=lambda err: self.ventana.manejar_error(err, self.aviso), contexto=self)

    def borrar(self, actividad: dict) -> None:
        if not dialogos.confirmar(self, "Eliminar actividad", "¿Eliminar esta actividad y sus evidencias? "
                                  "No se puede deshacer.", "Eliminar", peligro=True):
            return
        ejecutar(self.e.api.borrar_actividad, actividad["id"], al_ok=lambda _: self._hecho("Eliminamos la actividad."),
                 al_error=lambda err: self.ventana.manejar_error(err, self.aviso), contexto=self)

    def _hecho(self, mensaje: str) -> None:
        self.aviso.mostrar(mensaje, "exito")
        self.e.actividades_cambiadas.emit()
        self.cargar()
