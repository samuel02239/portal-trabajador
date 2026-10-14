"""Inicio: contrato, periodo actual, indicadores, cuadro para la actividad del día y avance por obligación."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel

from app import config
from app.estado import estado
from app.servicios.hilos import ejecutar
from app.widgets import boton, icono, plural
from app.widgets.aviso import Aviso
from app.widgets.campos import AreaTexto, CampoFecha
from app.widgets.carga import Indicador
from app.widgets.grafico_avance import GraficoAvance
from app.widgets.indicador_kpi import IndicadorKpi
from app.widgets.medidor_cupo import texto_cupo
from app.widgets.tarjeta import PaginaDesplazable, Tarjeta


class VentanaInicio(PaginaDesplazable):
    def __init__(self, ventana):
        super().__init__(ancho_max=1120)
        self.ventana = ventana
        self.e = estado()
        c = self.capa
        self.saludo = QLabel("Hola")
        self.saludo.setProperty("rol", "titulo")
        self.contexto = QLabel()
        self.contexto.setProperty("rol", "secundario")
        self.contexto.setWordWrap(True)
        c.addWidget(self.saludo)
        c.addWidget(self.contexto)
        self.aviso = Aviso()
        c.addWidget(self.aviso)

        kpis = QHBoxLayout()
        kpis.setSpacing(14)
        self.k_actividades = IndicadorKpi("Actividades del periodo", "fa6s.list-check")
        self.k_cubiertas = IndicadorKpi("Obligaciones cubiertas", "fa6s.chart-simple")
        self.k_informes = IndicadorKpi("Informes disponibles", "fa6s.file-circle-check")
        self.k_cierre = IndicadorKpi("Cierre del periodo", "fa6s.calendar-days")
        for k in (self.k_actividades, self.k_cubiertas, self.k_informes, self.k_cierre):
            kpis.addWidget(k, 1)
        c.addLayout(kpis)

        hoy = Tarjeta("¿Qué hiciste hoy?", "Cuéntalo con tus palabras; nosotros lo ubicamos en tus obligaciones "
                                          "y lo redactamos.")
        self.texto = AreaTexto("Actividad", "Ej.: hoy hice mantenimiento a los computadores de la oficina",
                               maximo=config.MAX_ACTIVIDAD, alto=84)
        self.texto.campo.setMaximumHeight(130)
        hoy.agregar(self.texto)
        fila = QHBoxLayout()
        self.fecha = CampoFecha("Fecha", opcional=False)
        self.fecha.setMaximumWidth(200)
        self.ubicar = boton("Ubicar en mi informe", "primario", icono("fa6s.wand-magic-sparkles", "#FFFFFF"))
        self.ubicar.setToolTip("Ubicar en mi informe (Ctrl+Enter)")
        self.ubicar.clicked.connect(self._ubicar)
        fila.addWidget(self.fecha)
        fila.addStretch(1)
        fila.addWidget(self.ubicar, 0, Qt.AlignBottom)
        hoy.capa.addLayout(fila)
        QShortcut(QKeySequence("Ctrl+Return"), self.texto.campo, activated=self._ubicar)
        c.addWidget(hoy)

        avance = Tarjeta("Avance por obligación")
        self.periodo = QLabel()
        self.periodo.setProperty("rol", "secundario")
        avance.agregar(self.periodo)
        self.indicador = Indicador("Cargando tu avance…")
        avance.agregar(self.indicador)
        self.grafico = GraficoAvance()
        avance.agregar(self.grafico)
        pie = QHBoxLayout()
        ver = boton("Ver mi informe")
        ver.clicked.connect(lambda: self.ventana.ir("informe"))
        generar = boton("Generar informe", "primario")
        generar.setToolTip("Generar informe (Ctrl+G)")
        generar.clicked.connect(lambda: self.ventana.ir("generar"))
        pie.addStretch(1)
        pie.addWidget(ver)
        pie.addWidget(generar)
        avance.capa.addLayout(pie)
        c.addWidget(avance)

        self.e.actividades_cambiadas.connect(self._marcar_viejo)
        self.e.contrato_cambiado.connect(self._marcar_viejo)
        self.e.suscripcion_cambiada.connect(self._pintar_cupo)
        self._viejo = True

    def _marcar_viejo(self) -> None:
        self._viejo = True

    def al_mostrar(self, **_) -> None:
        nombre = self.e.nombre_corto()
        self.saludo.setText(f"Hola, {nombre}" if nombre else "Hola")
        self._poner_contexto()
        self._pintar_cupo()
        self.texto.campo.setFocus()
        if self._viejo:
            self.cargar()

    def _poner_contexto(self, periodo: str | None = None) -> None:
        c = self.e.contrato or {}
        lugar = c.get("dependencia") or c.get("proyecto") or ""
        if lugar.isupper():
            lugar = lugar.capitalize()
        partes = [f"Contrato {c['numero_contrato']}" if c.get("numero_contrato") else "Contrato sin número",
                  lugar, f"Periodo: {periodo}" if periodo else ""]
        self.contexto.setText(" · ".join(x for x in partes if x))

    def _pintar_cupo(self) -> None:
        s = self.e.suscripcion
        if not s:
            self.k_informes.poner("—", "Cargando tu plan…")
        elif s.get("limite") is None:
            self.k_informes.poner("Sin límite", texto_cupo(s).split(" · ")[0])
        else:
            restantes = s.get("restantes") or 0
            if restantes == 0:
                self.k_informes.poner(f"0 de {s['limite']}", "Sin informes disponibles: revisa los planes",
                                      "advertencia")
            else:
                self.k_informes.poner(f"{restantes} de {s['limite']}", texto_cupo(s).split(" · ")[0])

    def cargar(self) -> None:
        self.indicador.mostrar()
        ejecutar(self.e.api.informe_actual, al_ok=self._poner,
                 al_error=lambda err: self.ventana.manejar_error(err, self.aviso),
                 al_final=self.indicador.ocultar, contexto=self)

    def _poner(self, d: dict) -> None:
        self._viejo = False
        p = d["periodo"]
        self._poner_contexto(p["etiqueta"].lower())
        k = d["conteo"]
        self.k_actividades.poner(str(k["confirmadas"]), f"Confirmadas en {p['etiqueta'].lower()} · "
                                                        f"{plural(k['total'], 'registrada')}")
        total = len(d["obligaciones"])
        cubiertas = sum(1 for o in d["obligaciones"] if o.get("confirmadas"))
        self.k_cubiertas.poner(f"{cubiertas} de {total}", "Con al menos una actividad confirmada")
        fin = date.fromisoformat(p["fin"])
        dias = (fin - date.today()).days
        if dias < 0:
            self.k_cierre.poner("Cerrado", f"Terminó el {fin:%d/%m/%Y}")
        elif dias <= 3:
            self.k_cierre.poner(plural(dias, "día"), f"Cierra el {fin:%d/%m/%Y}: prepara tu informe", "advertencia")
        else:
            self.k_cierre.poner(plural(dias, "día"), f"Hasta el {fin:%d/%m/%Y}")
        self.periodo.setText(f"Actividades confirmadas por obligación en {p['etiqueta'].lower()}. "
                             "Pasa el cursor sobre una fila para ver la obligación completa.")
        self.grafico.poner(d["obligaciones"])
        graves = [a for a in d["alertas"] if a["nivel"] == "error"]
        if graves:
            self.aviso.mostrar(" ".join(a["mensaje"] for a in graves), "error")
        else:
            self.aviso.ocultar()

    def _ubicar(self) -> None:
        texto = self.texto.texto()
        if len(texto) < 3:
            self.texto.error("Escribe qué hiciste (al menos unas palabras).")
            return
        self.ventana.ir("actividad", texto=texto, fecha=self.fecha.fecha(), clasificar=True)
        self.texto.poner("")
