"""Generar y descargar: alertas pendientes, cupo, vista previa del PDF y guardado en Word/PDF."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import QStandardPaths, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QFileDialog, QHBoxLayout, QLabel, QVBoxLayout

from app.estado import estado
from app.servicios.hilos import ejecutar
from app.ventanas.informe import SelectorPeriodo, alertas_resumidas
from app.widgets import icono, boton, mostrar_en
from app.widgets.aviso import Aviso
from app.widgets.campos import CampoFecha
from app.widgets.carga import Indicador
from app.widgets.medidor_cupo import MedidorCupo
from app.widgets.tarjeta import PaginaDesplazable, Tarjeta
from app.widgets.visor_pdf import VisorPdf


class VentanaGenerar(PaginaDesplazable):
    def __init__(self, ventana):
        super().__init__(ancho_max=1100)
        self.ventana = ventana
        self.e = estado()
        self.datos: dict | None = None
        self.ultimo_guardado: Path | None = None
        c = self.capa
        cab = QHBoxLayout()
        titulo = QLabel("Generar y descargar")
        titulo.setProperty("rol", "titulo")
        self.selector = SelectorPeriodo()
        self.selector.currentIndexChanged.connect(lambda _: self._cambiar_periodo())
        cab.addWidget(titulo)
        cab.addStretch(1)
        et = QLabel("Periodo:")
        et.setBuddy(self.selector)
        cab.addWidget(et)
        cab.addWidget(self.selector)
        c.addLayout(cab)

        fila = QHBoxLayout()
        fila.setSpacing(16)
        izq = Tarjeta("Antes de generar")
        izq.setMaximumWidth(400)
        self.medidor = MedidorCupo(compacto=False)
        izq.agregar(self.medidor)
        self.alertas = QVBoxLayout()
        izq.capa.addLayout(self.alertas)
        self.final = QCheckBox("Marcar como informe final")
        self.final.setToolTip("Úsalo para el último informe del contrato.")
        izq.agregar(self.final)
        self.fecha = CampoFecha("Fecha de elaboración", opcional=False)
        izq.agregar(self.fecha)
        self.aviso = Aviso(cerrable=True)
        izq.agregar(self.aviso)
        self.indicador = Indicador()
        izq.agregar(self.indicador)
        self.b_generar = boton("Generar informe", "primario", qta.icon("fa6s.file-export", color="#FFFFFF"))
        self.b_generar.setToolTip("Generar informe (Ctrl+G)")
        self.b_generar.clicked.connect(self._generar)
        izq.agregar(self.b_generar)
        nota = QLabel("Registrar actividades no gasta cupo; solo generar el informe. Volver a generar un informe "
                      "que ya generaste este mes no gasta otro.")
        nota.setProperty("rol", "secundario")
        nota.setWordWrap(True)
        izq.agregar(nota)
        izq.capa.addStretch(1)

        der = Tarjeta("Vista previa")
        self.estado_previa = QLabel("Genera el informe para verlo aquí antes de guardarlo.")
        self.estado_previa.setProperty("rol", "secundario")
        self.estado_previa.setWordWrap(True)
        der.agregar(self.estado_previa)
        self.advertencias = QVBoxLayout()
        der.capa.addLayout(self.advertencias)
        self.visor = VisorPdf()
        self.visor.hide()
        der.agregar(self.visor, 1)
        botones = QHBoxLayout()
        self.b_word = boton("Guardar Word", "secundario", icono("fa6s.file-word"))
        self.b_pdf = boton("Guardar PDF", "primario", qta.icon("fa6s.file-pdf", color="#FFFFFF"))
        self.b_word.clicked.connect(lambda: self._guardar("docx"))
        self.b_pdf.clicked.connect(lambda: self._guardar("pdf"))
        self.b_abrir = boton("Abrir el archivo guardado", "enlace")
        self.b_abrir.clicked.connect(self._abrir)
        self.b_abrir.hide()
        botones.addWidget(self.b_abrir)
        botones.addStretch(1)
        botones.addWidget(self.b_word)
        botones.addWidget(self.b_pdf)
        der.capa.addLayout(botones)
        fila.addWidget(izq)
        fila.addWidget(der, 1)
        c.addLayout(fila)

        self.e.suscripcion_cambiada.connect(lambda: self.medidor.poner(self.e.suscripcion))
        self._viejo = True
        self.e.actividades_cambiadas.connect(lambda: setattr(self, "_viejo", True))
        self.e.contrato_cambiado.connect(lambda: setattr(self, "_viejo", True))
        self.e.periodo_cambiado.connect(lambda _: setattr(self, "_viejo", True))

    # ------------------------------------------------------------------
    def al_mostrar(self, **_) -> None:
        self.medidor.poner(self.e.suscripcion)
        self.fecha.poner(date.today())
        if self._viejo:
            self.cargar()
        self.b_generar.setFocus()

    def _cambiar_periodo(self) -> None:
        clave = self.selector.currentData()
        if clave:
            self.e.poner_periodo(clave)
            self.cargar()

    def _botones_descarga(self, d: dict | None) -> None:
        inf = (d or {}).get("informe") or {}
        self.b_word.setEnabled(bool(inf.get("docx_path")))
        self.b_pdf.setEnabled(bool(inf.get("pdf_path")))

    def cargar(self) -> None:
        self.indicador.mostrar("Revisando tu informe…")
        self.visor.hide()
        self._botones_descarga(None)
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
        self._limpiar(self.alertas)
        resumen = alertas_resumidas(d["alertas"])
        if resumen:
            t = QLabel("Alertas pendientes:")
            t.setProperty("rol", "seccion")
            mostrar_en(self.alertas, t)
        for texto, nivel in resumen:
            mostrar_en(self.alertas, Aviso(texto, nivel))
        hay = d["conteo"]["confirmadas"] > 0
        self.b_generar.setEnabled(hay)
        if not hay:
            self.aviso.mostrar("Para generar el informe necesitas al menos una actividad confirmada en este periodo.",
                               "info", accion="Registrar actividad")
            try:
                self.aviso.accion.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.aviso.accion.connect(lambda: self.ventana.ir("actividad"))
        else:
            self.aviso.ocultar()
        inf = d["informe"]
        self.final.setChecked(inf.get("tipo") == "final")
        self._botones_descarga(d)
        if inf.get("pdf_path"):
            self.estado_previa.setText("Este informe ya fue generado. Esta es la última versión.")
            self._cargar_previa(inf["id"])
        else:
            self.estado_previa.setText("Genera el informe para verlo aquí antes de guardarlo.")

    def _cargar_previa(self, informe_id: str) -> None:
        self.indicador.mostrar("Cargando la vista previa…")
        ejecutar(self.e.api.descargar_informe, informe_id, "pdf", al_ok=lambda r: self._mostrar_pdf(r[1]),
                 al_error=lambda err: self.estado_previa.setText(f"No se pudo cargar la vista previa: {err}"),
                 al_final=self.indicador.ocultar, contexto=self)

    def _mostrar_pdf(self, contenido: bytes) -> None:
        if self.visor.cargar(contenido):
            self.visor.show()

    def _generar(self) -> None:
        if not self.datos:
            return
        self.aviso.ocultar()
        self._limpiar(self.advertencias)
        self.b_generar.setEnabled(False)
        self.indicador.mostrar("Generando tu informe… (puede tardar unos segundos)")
        ejecutar(self.e.api.generar_informe, self.datos["informe"]["id"],
                 "final" if self.final.isChecked() else "parcial", self.fecha.iso(),
                 al_ok=self._generado, al_error=self._error_generar,
                 al_final=lambda: (self.indicador.ocultar(), self.b_generar.setEnabled(True)), contexto=self)

    def _generado(self, r: dict) -> None:
        self.e.poner_suscripcion(r.get("suscripcion"))
        self.datos["informe"] = r["informe"]
        self._botones_descarga(self.datos)
        if r.get("sin_limite"):
            detalle = " Cuenta de pruebas: no se descuenta cupo."
        elif r.get("cobrado"):
            detalle = ""
        else:
            detalle = " No se descontó cupo (ya estaba cobrado este mes)."
        texto = "Informe generado." + detalle
        self.aviso.mostrar(texto + " Revísalo en la vista previa y guárdalo.", "exito")
        for a in r.get("advertencias") or []:
            mostrar_en(self.advertencias, Aviso(a, "advertencia"))
        self.estado_previa.setText("Vista previa del informe generado:")
        if r.get("pdf"):
            self._cargar_previa(r["informe"]["id"])
        self.e.actividades_cambiadas.emit()
        self._viejo = False

    def _error_generar(self, err) -> None:
        if getattr(err, "codigo", "") == "limite_alcanzado":
            self.ventana.recargar_suscripcion()
            self.ventana.ir("planes", mensaje=str(err))
        else:
            self.ventana.manejar_error(err, self.aviso)

    def _guardar(self, formato: str) -> None:
        if not self.datos:
            return
        self.indicador.mostrar("Descargando…")
        ejecutar(self.e.api.descargar_informe, self.datos["informe"]["id"], formato,
                 al_ok=lambda r: self._elegir_destino(*r), al_error=lambda err: self.ventana.manejar_error(err, self.aviso),
                 al_final=self.indicador.ocultar, contexto=self)

    def _elegir_destino(self, nombre: str, contenido: bytes) -> None:
        carpeta = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        filtro = "Documento de Word (*.docx)" if nombre.endswith(".docx") else "PDF (*.pdf)"
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar informe", str(Path(carpeta) / nombre), filtro)
        if not ruta:
            return
        try:
            Path(ruta).write_bytes(contenido)
        except OSError:
            self.aviso.mostrar("No se pudo guardar el archivo. ¿Está abierto en otro programa?", "error")
            return
        self.ultimo_guardado = Path(ruta)
        self.b_abrir.show()
        self.aviso.mostrar(f"Guardado en {ruta}", "exito")

    def _abrir(self) -> None:
        if self.ultimo_guardado and self.ultimo_guardado.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.ultimo_guardado)))
