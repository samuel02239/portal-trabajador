"""Registrar actividad y propuesta de la IA (sección 7.3).

Reglas sobre la respuesta:
- Confianza ≥ 0.75: propuesta principal, lista para aceptar con un toque.
- Entre 0.45 y 0.75: aviso "Revisa si es la obligación correcta" y las 2 mejores alternativas.
- < 0.45 o sin coincidencia: "Esta actividad no parece estar entre tus obligaciones"; se guarda como
  sin_obligacion y no sale en el informe salvo que el usuario la asigne a mano.
El usuario siempre puede cambiar la obligación y editar la redacción antes de guardar.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QStackedWidget, QVBoxLayout, QWidget)

from app import config
from app.estado import estado
from app.servicios import archivos_locales
from app.servicios.hilos import ejecutar
from app.widgets import icono, boton, mostrar_en
from app.widgets.aviso import Aviso
from app.widgets.campos import AreaTexto, CampoFecha
from app.widgets.carga import Indicador
from app.widgets.insignia import Insignia
from app.widgets.tarjeta import PanelCentrado

UMBRAL_ALTO = 0.75
UMBRAL_BAJO = 0.45
MENSAJE_IA_CAIDA = "No pudimos analizar esto ahora; guarda tu actividad y reintenta."
EXTENSIONES_EVIDENCIA = "Evidencias (*.pdf *.docx *.png *.jpg *.jpeg *.xlsx)"


def nivel(confianza: float | None, sin_coincidencia: bool = False) -> str:
    if sin_coincidencia or confianza is None or confianza < UMBRAL_BAJO:
        return "baja"
    return "alta" if confianza >= UMBRAL_ALTO else "media"


def titulo_obligacion(o: dict) -> str:
    return f"{o['numero']}. {o.get('titulo_corto') or o['texto'][:50]}"


class PanelPropuesta(QWidget):
    """Muestra la propuesta y arma lo que se va a guardar. No llama a la red."""
    guardar = Signal()
    descartar = Signal()
    editar_texto = Signal()
    reintentar = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.respuesta: dict = {}
        self.texto_original = ""
        self.manual = False
        self.obligaciones: list[dict] = []
        c = QVBoxLayout(self)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(10)

        t = QLabel("Tu texto:")
        t.setProperty("rol", "seccion")
        self.cita = QLabel()
        self.cita.setProperty("rol", "cita")
        self.cita.setWordWrap(True)
        self.banner = Aviso()
        self.encaja = QLabel()
        self.encaja.setProperty("rol", "grande")
        self.encaja.setWordWrap(True)
        fila_conf = QHBoxLayout()
        self.confianza = QLabel()
        self.insignia = Insignia()
        fila_conf.addWidget(self.confianza)
        fila_conf.addWidget(self.insignia)
        fila_conf.addStretch(1)
        self.justificacion = QLabel()
        self.justificacion.setProperty("rol", "secundario")
        self.justificacion.setWordWrap(True)
        self.alternativas_caja = QWidget()
        self.alternativas = QVBoxLayout(self.alternativas_caja)
        self.alternativas.setContentsMargins(0, 0, 0, 0)

        r = QLabel("Redacción sugerida (puedes editarla):")
        r.setProperty("rol", "seccion")
        self.redaccion = QPlainTextEdit()
        self.redaccion.setMinimumHeight(110)
        self.redaccion.setTabChangesFocus(True)
        self.redaccion.setAccessibleName("Redacción de la actividad")
        r.setBuddy(self.redaccion)

        o = QLabel("Obligación:")
        o.setProperty("rol", "seccion")
        self.combo = QComboBox()
        self.combo.setAccessibleName("Cambiar obligación")
        o.setBuddy(self.combo)
        self.combo.currentIndexChanged.connect(self._combo_cambio)

        self.extras_caja = QWidget()
        self.extras = QVBoxLayout(self.extras_caja)
        self.extras.setContentsMargins(0, 0, 0, 0)
        self.casillas_extra: list[tuple[QCheckBox, dict]] = []

        self.pregunta = Aviso()
        self.pregunta.accion.connect(self.editar_texto.emit)

        botones = QHBoxLayout()
        self.b_reintentar = boton("Reintentar análisis", "secundario")
        self.b_reintentar.clicked.connect(self.reintentar.emit)
        b_descartar = boton("Descartar", "secundario")
        b_descartar.clicked.connect(self.descartar.emit)
        self.b_guardar = boton("Guardar", "primario")
        self.b_guardar.clicked.connect(self.guardar.emit)
        botones.addWidget(self.b_reintentar)
        botones.addStretch(1)
        botones.addWidget(b_descartar)
        botones.addWidget(self.b_guardar)

        for w in (t, self.cita, self.banner, self.encaja):
            c.addWidget(w)
        c.addLayout(fila_conf)
        for w in (self.justificacion, self.alternativas_caja, r, self.redaccion, o, self.combo, self.extras_caja,
                  self.pregunta):
            c.addWidget(w)
        c.addLayout(botones)

    # ------------------------------------------------------------------
    def _llenar_combo(self, seleccion: str | None) -> None:
        self.combo.blockSignals(True)
        self.combo.clear()
        for o in self.obligaciones:
            self.combo.addItem(titulo_obligacion(o), o["id"])
            self.combo.setItemData(self.combo.count() - 1, o["texto"], Qt.ToolTipRole)
        self.combo.addItem("Sin obligación (no sale en el informe)", None)
        i = self.combo.findData(seleccion)
        self.combo.setCurrentIndex(i if i >= 0 else self.combo.count() - 1)
        self.combo.blockSignals(False)

    def _limpiar(self, capa) -> None:
        while capa.count():
            w = capa.takeAt(0).widget()
            if w:
                w.deleteLater()

    def mostrar(self, respuesta: dict, texto_original: str, obligaciones: list[dict]) -> None:
        self.respuesta, self.texto_original, self.obligaciones, self.manual = respuesta, texto_original, obligaciones, False
        self.cita.setText(f"“{texto_original}”")
        asign = respuesta.get("asignaciones") or []
        principal = asign[0] if asign else None
        n = nivel(principal["confianza"] if principal else None, respuesta.get("sin_coincidencia", False))
        self._limpiar(self.alternativas)
        self._limpiar(self.extras)
        self.casillas_extra = []
        self.b_reintentar.hide()

        if n == "baja":
            self.banner.mostrar("Esta actividad no parece estar entre tus obligaciones. Puedes guardarla sin "
                                "obligación (no saldrá en el informe) o elegir una a mano.", "advertencia")
            self.encaja.setText("No encaja en tus obligaciones")
            self._llenar_combo(None)
        else:
            self.encaja.setText(f"Encaja en: Obligación {principal['obligacion_numero']}")
            self.encaja.setToolTip(principal.get("obligacion_texto", ""))
            self._llenar_combo(principal["obligacion_id"])
            if n == "media":
                self.banner.mostrar("Revisa si es la obligación correcta.", "advertencia")
                otras = asign[1:3]
                if otras:
                    t = QLabel("Otras opciones:")
                    t.setProperty("rol", "secundario")
                    mostrar_en(self.alternativas, t)
                for a in otras:
                    b = boton(f"Usar obligación {a['obligacion_numero']} ({round(a['confianza'] * 100)} %)", "secundario")
                    b.setToolTip(a.get("obligacion_texto", ""))
                    b.clicked.connect(lambda _=False, a=a: self.usar(a))
                    mostrar_en(self.alternativas, b)
            else:
                self.banner.mostrar("Lista para guardar. Revisa la redacción si quieres.", "exito")
                for a in asign[1:3]:
                    if a["confianza"] >= UMBRAL_ALTO:
                        caja = QCheckBox(f"Guardar también en la obligación {a['obligacion_numero']} "
                                         f"({round(a['confianza'] * 100)} %)")
                        caja.setToolTip(a.get("obligacion_texto", ""))
                        mostrar_en(self.extras, caja)
                        self.casillas_extra.append((caja, a))
        self.alternativas_caja.setVisible(n == "media" and len(asign) > 1)
        self.extras_caja.setVisible(bool(self.casillas_extra))

        conf = principal["confianza"] if principal else 0
        self.confianza.setText(f"Confianza: {round(conf * 100)} %" if principal else "")
        self.insignia.poner(n)
        self.justificacion.setText(principal.get("justificacion", "") if principal else "")
        self.redaccion.setPlainText(principal["redaccion"] if principal else texto_original)
        if respuesta.get("pregunta_aclaracion"):
            self.pregunta.mostrar(f"Para precisar la redacción: {respuesta['pregunta_aclaracion']}", "info",
                                  accion="Editar mi texto")
        else:
            self.pregunta.ocultar()
        self.b_guardar.setFocus()

    def mostrar_manual(self, texto_original: str, obligaciones: list[dict], motivo: str = MENSAJE_IA_CAIDA) -> None:
        """Sin IA: el usuario elige la obligación y redacta él mismo."""
        self.respuesta, self.texto_original, self.obligaciones, self.manual = {}, texto_original, obligaciones, True
        self.cita.setText(f"“{texto_original}”")
        self.banner.mostrar(motivo, "advertencia")
        self.encaja.setText("Elige la obligación")
        self.encaja.setToolTip("")
        self.confianza.setText("")
        self.insignia.poner("neutra", "Sin analizar")
        self.justificacion.setText("Si no eliges ninguna, la actividad queda guardada sin clasificar y podrás "
                                   "ubicarla después en Mi informe.")
        self._limpiar(self.alternativas)
        self._limpiar(self.extras)
        self.casillas_extra = []
        self.alternativas_caja.hide()
        self.extras_caja.hide()
        self.pregunta.ocultar()
        self.b_reintentar.show()
        self.redaccion.setPlainText(texto_original)
        self._llenar_combo(None)

    def usar(self, asignacion: dict) -> None:
        i = self.combo.findData(asignacion["obligacion_id"])
        if i >= 0:
            self.combo.setCurrentIndex(i)
        self.redaccion.setPlainText(asignacion["redaccion"])

    def _combo_cambio(self, _i: int) -> None:
        # Si el usuario elige una obligación que la IA propuso, se usa la redacción de esa propuesta
        elegido = self.combo.currentData()
        for a in self.respuesta.get("asignaciones") or []:
            if a["obligacion_id"] == elegido and self.redaccion.toPlainText().strip() in (
                    "", *[x["redaccion"] for x in self.respuesta["asignaciones"]]):
                self.redaccion.setPlainText(a["redaccion"])

    def datos(self, fecha: date) -> list[dict]:
        """Actividades a guardar: la principal y las adicionales marcadas."""
        elegido = self.combo.currentData()
        asign = {a["obligacion_id"]: a for a in self.respuesta.get("asignaciones") or []}
        redaccion = self.redaccion.toPlainText().strip() or self.texto_original
        if elegido:
            estado_ = "confirmada"
        elif self.manual:
            estado_ = "propuesta"      # sin clasificar: se puede ubicar después
        else:
            estado_ = "sin_obligacion"
        principal = {
            "fecha": fecha.isoformat(), "texto_original": self.texto_original, "texto_redactado": redaccion,
            "obligacion_id": elegido, "confianza": asign[elegido]["confianza"] if elegido in asign else None,
            "estado": estado_, "modelo_usado": self.respuesta.get("modelo"),
        }
        salida = [principal]
        for caja, a in self.casillas_extra:
            if caja.isChecked() and a["obligacion_id"] != elegido:
                salida.append({**principal, "obligacion_id": a["obligacion_id"], "texto_redactado": a["redaccion"],
                               "confianza": a["confianza"], "estado": "confirmada"})
        return salida


class VentanaActividad(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.ventana = ventana
        self.e = estado()
        self.evidencias: list[str] = []
        self.pila = QStackedWidget(self)
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.addWidget(self.pila)

        # --- Formulario
        self.form = PanelCentrado(620)
        f = self.form.capa
        titulo = QLabel("Registrar actividad")
        titulo.setProperty("rol", "titulo")
        self.aviso = Aviso(cerrable=True)
        self.texto = AreaTexto("¿Qué hiciste?", "Ej.: hoy hice mantenimiento a los computadores de la oficina",
                               maximo=config.MAX_ACTIVIDAD, alto=120)
        self.fecha = CampoFecha("Fecha de la actividad", opcional=False)
        self.fecha.setMaximumWidth(220)
        ev = QLabel("Evidencias (opcional): fotos, actas, listados…")
        ev.setProperty("rol", "seccion")
        ayuda_ev = QLabel("Se guarda una copia en tu carpeta de evidencias, se adjunta como anexo con una descripción "
                          "acorde a la actividad. Las fotos y también los PDF, Word y Excel se pegan al final del informe como "
                          "capturas de pantalla de cada hoja: no necesitas convertirlos en imagen.")
        ayuda_ev.setProperty("rol", "secundario")
        ayuda_ev.setWordWrap(True)
        self.lista_ev = QListWidget()
        self.lista_ev.setIconSize(QSize(56, 56))
        self.lista_ev.setMaximumHeight(150)
        self.lista_ev.setAccessibleName("Evidencias adjuntas")
        self.lista_ev.hide()
        fila_ev = QHBoxLayout()
        adjuntar = boton("Adjuntar evidencia", "secundario", icono("fa6s.paperclip"))
        quitar = boton("Quitar seleccionada", "enlace")
        carpeta = boton("Abrir carpeta de evidencias", "enlace")
        adjuntar.clicked.connect(self._adjuntar)
        quitar.clicked.connect(self._quitar_evidencia)
        carpeta.clicked.connect(self._abrir_carpeta)
        fila_ev.addWidget(adjuntar)
        fila_ev.addWidget(quitar)
        fila_ev.addStretch(1)
        fila_ev.addWidget(carpeta)
        self.indicador = Indicador()
        botones = QHBoxLayout()
        self.b_manual = boton("Guardar sin analizar", "secundario")
        self.b_manual.clicked.connect(lambda: self._mostrar_manual("Elige tú la obligación y escribe la redacción."))
        self.b_ubicar = boton("Ubicar en mi informe", "primario", qta.icon("fa6s.wand-magic-sparkles", color="#FFFFFF"))
        self.b_ubicar.setToolTip("Ubicar en mi informe (Ctrl+Enter)")
        self.b_ubicar.clicked.connect(self._clasificar)
        botones.addWidget(self.b_manual)
        botones.addStretch(1)
        botones.addWidget(self.b_ubicar)
        for w in (titulo, self.aviso, self.texto, self.fecha, ev, ayuda_ev, self.lista_ev):
            f.addWidget(w)
        f.addLayout(fila_ev)
        f.addWidget(self.indicador)
        f.addLayout(botones)
        QShortcut(QKeySequence("Ctrl+Return"), self.texto.campo, activated=self._clasificar)
        self.pila.addWidget(self.form)

        # --- Propuesta (panel centrado de unos 480 px)
        self.prop_pagina = PanelCentrado(500)
        tp = QLabel("Propuesta")
        tp.setProperty("rol", "titulo")
        self.prop_pagina.capa.addWidget(tp)
        self.propuesta = PanelPropuesta()
        self.prop_pagina.capa.addWidget(self.propuesta)
        self.aviso_prop = Aviso()
        self.indicador_prop = Indicador("Guardando…")
        self.prop_pagina.capa.addWidget(self.aviso_prop)
        self.prop_pagina.capa.addWidget(self.indicador_prop)
        self.pila.addWidget(self.prop_pagina)
        self.propuesta.guardar.connect(self._guardar)
        self.propuesta.descartar.connect(self._descartar)
        self.propuesta.editar_texto.connect(lambda: self.pila.setCurrentWidget(self.form))
        self.propuesta.reintentar.connect(self._clasificar)

    # ------------------------------------------------------------------
    def al_mostrar(self, texto: str | None = None, fecha: date | None = None, clasificar: bool = False, **_) -> None:
        if texto:
            self.texto.poner(texto)
            self.fecha.poner(fecha or date.today())
            self.pila.setCurrentWidget(self.form)
            if clasificar:
                self._clasificar()
                return
        if self.pila.currentWidget() is self.form:
            self.texto.campo.setFocus()

    def _adjuntar(self) -> None:
        rutas, _ = QFileDialog.getOpenFileNames(self, "Adjuntar evidencias", "", EXTENSIONES_EVIDENCIA)
        self.agregar_evidencias(rutas)

    def agregar_evidencias(self, rutas: list[str]) -> None:
        """Guarda una copia local de cada archivo y la deja lista para subirla con la actividad."""
        guardadas = []
        for r in rutas:
            p = Path(r)
            if p.stat().st_size > config.MAX_ARCHIVO:
                self.aviso.mostrar(f"{p.name} supera el máximo de 20 MB.", "error")
                continue
            try:
                copia = archivos_locales.guardar_copia(p, self.fecha.fecha())
            except OSError as exc:
                self.aviso.mostrar(f"No se pudo guardar una copia de {p.name}: {exc}", "error")
                continue
            if str(copia) in self.evidencias:
                continue
            self.evidencias.append(str(copia))
            imagen = archivos_locales.es_imagen(copia)
            item = QListWidgetItem(QIcon(str(copia)) if imagen else icono("fa6s.paperclip"), p.name, self.lista_ev)
            item.setData(Qt.UserRole, str(copia))
            item.setToolTip(f"Copia guardada en: {copia}")
            guardadas.append(copia)
        self.lista_ev.setVisible(bool(self.evidencias))
        if guardadas:
            n = len(guardadas)
            self.aviso.mostrar(f"Guardamos una copia de {n} archivo{'s' if n > 1 else ''} en tu carpeta de evidencias "
                               f"(Documentos › Portal del Trabajador › Evidencias › {guardadas[0].parent.name}).", "info")
            self.aviso.setToolTip(str(guardadas[0].parent))

    def _quitar_evidencia(self) -> None:
        for item in self.lista_ev.selectedItems():
            self.evidencias.remove(item.data(Qt.UserRole))
            self.lista_ev.takeItem(self.lista_ev.row(item))
        self.lista_ev.setVisible(bool(self.evidencias))

    def _abrir_carpeta(self) -> None:
        carpeta = archivos_locales.carpeta_del_mes(self.fecha.fecha())
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(carpeta)))

    def _ocupado(self, si: bool, texto: str = "") -> None:
        self.b_ubicar.setEnabled(not si)
        self.b_manual.setEnabled(not si)
        self.indicador.mostrar(texto) if si else self.indicador.ocultar()

    def _validar(self) -> bool:
        if len(self.texto.texto()) < 3:
            self.texto.error("Escribe qué hiciste (al menos unas palabras).")
            self.pila.setCurrentWidget(self.form)
            return False
        return True

    def _clasificar(self) -> None:
        if not self._validar():
            return
        self.pila.setCurrentWidget(self.form)
        self.aviso.ocultar()
        self._ocupado(True, "Ubicando tu actividad en tus obligaciones…")
        ejecutar(self.e.api.clasificar, self.texto.texto(), self.fecha.fecha().isoformat(),
                 al_ok=self._propuesta_lista, al_error=self._error_clasificar,
                 al_final=lambda: self._ocupado(False), contexto=self)

    def _aviso_evidencias(self) -> None:
        if self.evidencias:
            n = len(self.evidencias)
            self.aviso_prop.mostrar(f"Al guardar se adjuntará{'n' if n > 1 else ''} {n} evidencia{'s' if n > 1 else ''} "
                                    "como anexo. Escribiremos la descripción de cada anexo según esta actividad y "
                                    "las fotos irán al final del informe.", "info")
        else:
            self.aviso_prop.ocultar()

    def _propuesta_lista(self, respuesta: dict) -> None:
        self._aviso_evidencias()
        self.propuesta.mostrar(respuesta, self.texto.texto(), self.e.especificas())
        self.pila.setCurrentWidget(self.prop_pagina)

    def _error_clasificar(self, err) -> None:
        codigo = getattr(err, "codigo", "")
        if codigo == "ia_no_disponible":
            self._mostrar_manual(MENSAJE_IA_CAIDA)
        elif codigo == "sin_contrato":
            self.ventana.mostrar_minuta()
        else:
            self.ventana.manejar_error(err, self.aviso)

    def _mostrar_manual(self, motivo: str) -> None:
        if not self._validar():
            return
        self._aviso_evidencias()
        self.propuesta.mostrar_manual(self.texto.texto(), self.e.especificas(), motivo)
        self.pila.setCurrentWidget(self.prop_pagina)

    def _descartar(self) -> None:
        self.pila.setCurrentWidget(self.form)
        self.texto.campo.setFocus()

    def _guardar(self) -> None:
        actividades = self.propuesta.datos(self.fecha.fecha())
        evidencias = list(self.evidencias)
        self.propuesta.b_guardar.setEnabled(False)
        self.indicador_prop.mostrar("Guardando…")
        api = self.e.api

        def guardar_todo():
            guardadas = [api.crear_actividad(a) for a in actividades]
            subidas, fallidas = [], []
            for ruta in evidencias:
                try:
                    subidas.append(api.subir_evidencia(guardadas[0]["id"], ruta))
                except Exception as exc:  # la actividad ya quedó guardada; se informa qué evidencia falló
                    fallidas.append(f"{Path(ruta).name}: {exc}")
            return guardadas, subidas, fallidas

        ejecutar(guardar_todo, al_ok=self._guardado, al_error=lambda err: self.ventana.manejar_error(err, self.aviso_prop),
                 al_final=self._fin_guardar, contexto=self)

    def _fin_guardar(self) -> None:
        self.propuesta.b_guardar.setEnabled(True)
        self.indicador_prop.ocultar()

    def _guardado(self, resultado) -> None:
        guardadas, subidas, fallidas = resultado
        principal = guardadas[0]
        numeros = {o["id"]: o["numero"] for o in self.e.obligaciones}
        if principal.get("obligacion_id"):
            lugares = ", ".join(str(numeros.get(a["obligacion_id"], "?")) for a in guardadas)
            texto = f"Guardamos tu actividad en la obligación {lugares}."
            nivel_aviso = "exito"
        elif principal["estado"] == "propuesta":
            texto = "Guardamos tu actividad sin clasificar. Ubícala después en Mi informe para que salga en el informe."
            nivel_aviso = "info"
        else:
            texto = "Guardamos tu actividad sin obligación: no saldrá en el informe salvo que la asignes en Mi informe."
            nivel_aviso = "info"
        if subidas:
            texto += " Anexos: " + "; ".join(f"«{e.get('descripcion') or e['nombre']}»" for e in subidas) + \
                     ". Puedes ajustar su descripción en Mi informe."
        if fallidas:
            texto += " No se pudieron subir algunas evidencias: " + "; ".join(fallidas)
            nivel_aviso = "advertencia"
        self.texto.poner("")
        self.evidencias.clear()
        self.lista_ev.clear()
        self.lista_ev.hide()
        self.fecha.poner(date.today())
        self.pila.setCurrentWidget(self.form)
        self.aviso.mostrar(texto, nivel_aviso)
        self.e.actividades_cambiadas.emit()
        self.texto.campo.setFocus()
