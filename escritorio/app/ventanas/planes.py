"""Planes y pago (Wompi). El pago ocurre en la página de la pasarela, en el navegador del sistema."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel

from app import tema
from app.estado import estado
from app.servicios.hilos import ejecutar
from app.widgets import boton, icono, mostrar_en
from app.widgets.aviso import Aviso
from app.widgets.carga import Indicador
from app.widgets.insignia import Insignia
from app.widgets.medidor_cupo import texto_cupo
from app.widgets.tarjeta import PaginaDesplazable, Tarjeta

INTERVALO_MS = 3000
ESPERA_MAXIMA_S = 10 * 60
CARACTERISTICAS = {
    "gratis": ["1 informe en total", "Prueba única al crear tu cuenta", "No vence"],
    "normal": ["2 informes al mes", "Vigencia de 30 días desde el pago", "Regenerar un informe no gasta cupo"],
    "pro": ["Informes ilimitados", "Vigencia de 30 días desde el pago", "Regenerar un informe no gasta cupo"],
}


def precio(cop: int) -> str:
    return "$0" if not cop else f"${cop:,.0f}".replace(",", ".")


class TarjetaPlan(Tarjeta):
    def __init__(self, plan: dict, actual: dict | None, al_pagar):
        super().__init__()
        self.setMinimumWidth(220)
        self.capa.setSpacing(10)
        nombre = QLabel(plan["nombre"])
        nombre.setProperty("rol", "subtitulo")
        fila_precio = QHBoxLayout()
        valor = QLabel(precio(plan["precio_cop"]))
        valor.setProperty("rol", "precio")
        unidad = QLabel("COP / mes" if plan["precio_cop"] else "")
        unidad.setProperty("rol", "secundario")
        fila_precio.addWidget(valor)
        fila_precio.addWidget(unidad, 0, Qt.AlignBottom)
        fila_precio.addStretch(1)
        self.agregar(nombre)
        self.capa.addLayout(fila_precio)
        separador = QLabel()
        separador.setObjectName("separador")
        self.agregar(separador)
        for linea in CARACTERISTICAS.get(plan["id"], []):
            f = QHBoxLayout()
            marca = QLabel()
            marca.setPixmap(icono("fa6s.circle-check", tema.ACTUAL["exito"]).pixmap(14, 14))
            texto = QLabel(linea)
            texto.setWordWrap(True)
            f.addWidget(marca, 0, Qt.AlignTop)
            f.addWidget(texto, 1)
            self.capa.addLayout(f)
        es_actual = bool(actual) and actual.get("plan") == plan["id"]
        if plan["id"] == "gratis":
            if es_actual and actual.get("restantes") == 0:
                self.capa.addWidget(Insignia("baja", "Agotado"), 0, Qt.AlignLeft)
            elif es_actual:
                self.capa.addWidget(Insignia("confirmada", "Tu plan"), 0, Qt.AlignLeft)
            self.capa.addStretch(1)
        else:
            if es_actual:
                fin = (actual.get("fin") or "")[:10]
                fin = f"{fin[8:10]}/{fin[5:7]}/{fin[:4]}" if fin else ""
                self.capa.addWidget(Insignia("confirmada", f"Tu plan · vence el {fin}" if fin else "Tu plan"), 0,
                                    Qt.AlignLeft)
            self.pagar = boton("Renovar" if es_actual else "Pagar", "primario")
            self.pagar.setAccessibleName(f"Pagar plan {plan['nombre']}")
            self.pagar.clicked.connect(lambda: al_pagar(plan))
            self.capa.addStretch(1)
            self.agregar(self.pagar)


class VentanaPlanes(PaginaDesplazable):
    def __init__(self, ventana):
        super().__init__()
        self.ventana = ventana
        self.e = estado()
        self.planes: list[dict] = []
        self.referencia: str | None = None
        self.inicio_espera = 0.0
        c = self.capa
        cab = QHBoxLayout()
        titulo = QLabel("Elige tu plan")
        titulo.setProperty("rol", "titulo")
        self.quedan = QLabel()
        self.quedan.setProperty("rol", "seccion")
        cab.addWidget(titulo)
        cab.addStretch(1)
        cab.addWidget(self.quedan)
        c.addLayout(cab)
        self.pruebas = Aviso("Estás usando una cuenta de pruebas: puedes generar todos los informes que necesites, "
                             "sin límite y sin pagar.", "info")
        self.pruebas.hide()
        c.addWidget(self.pruebas)
        self.aviso = Aviso(cerrable=True)
        c.addWidget(self.aviso)
        self.fila = QHBoxLayout()
        self.fila.setSpacing(16)
        c.addLayout(self.fila)
        self.indicador = Indicador()
        c.addWidget(self.indicador)

        self.espera = Tarjeta()
        fe = QHBoxLayout()
        self.ind_espera = Indicador("Esperando confirmación del pago…")
        self.ind_espera.show()
        self.verificar = boton("Ya pagué, verificar", "primario")
        self.verificar.clicked.connect(self._consultar)
        cancelar = boton("Dejar de esperar", "enlace")
        cancelar.clicked.connect(self._detener)
        fe.addWidget(self.ind_espera, 1)
        fe.addWidget(cancelar)
        fe.addWidget(self.verificar)
        self.espera.capa.addLayout(fe)
        self.espera.hide()
        c.addWidget(self.espera)

        nota = QLabel("El pago se hace en la página segura de Wompi, en tu navegador. Este programa nunca ve ni "
                      "guarda los datos de tu tarjeta. Cuando el pago se aprueba, tu plan se activa solo.")
        nota.setProperty("rol", "secundario")
        nota.setWordWrap(True)
        c.addWidget(nota)

        self.timer = QTimer(self)
        self.timer.setInterval(INTERVALO_MS)
        self.timer.timeout.connect(self._tick)
        self.e.suscripcion_cambiada.connect(self._pintar)

    # ------------------------------------------------------------------
    def al_mostrar(self, mensaje: str | None = None, **_) -> None:
        if mensaje:
            self.aviso.mostrar(mensaje, "advertencia")
        self.indicador.mostrar("Cargando planes…")

        def cargar():
            return self.e.api.planes()["planes"], self.e.api.suscripcion()

        ejecutar(cargar, al_ok=self._cargados, al_error=lambda err: self.ventana.manejar_error(err, self.aviso),
                 al_final=self.indicador.ocultar, contexto=self)

    def _cargados(self, r) -> None:
        self.planes, sus = r
        self.e.poner_suscripcion(sus)
        self._pintar()

    def _pintar(self) -> None:
        s = self.e.suscripcion
        if s:
            n = s.get("restantes") or 0
            self.quedan.setText("Informes ilimitados" if s.get("limite") is None
                                else ("Te queda 1 informe" if n == 1 else f"Te quedan {n} informes"))
            self.quedan.setAccessibleName(texto_cupo(s))
            self.pruebas.setVisible(bool(s.get("sin_limite")))
        while self.fila.count():
            w = self.fila.takeAt(0).widget()
            if w:
                w.deleteLater()
        for p in self.planes:
            mostrar_en(self.fila, TarjetaPlan(p, s, self._pagar), 1)

    def _pagar(self, plan: dict) -> None:
        self.aviso.ocultar()
        self.indicador.mostrar("Preparando el pago…")
        ejecutar(self.e.api.checkout, plan["id"], al_ok=self._abrir_pago, al_error=self._error_pago,
                 al_final=self.indicador.ocultar, contexto=self)

    def _abrir_pago(self, r: dict) -> None:
        self.referencia = r["referencia"]
        QDesktopServices.openUrl(QUrl(r["url"]))
        self.inicio_espera = time.monotonic()
        self.ind_espera.mostrar("Esperando confirmación del pago…")
        self.espera.show()
        self.timer.start()
        self.aviso.mostrar(f"Abrimos la página de pago en tu navegador (referencia {self.referencia}). "
                           "Cuando termines, vuelve aquí.", "info")

    def _error_pago(self, err) -> None:
        self.ventana.manejar_error(err, self.aviso)

    def _tick(self) -> None:
        """Consulta automática cada 3 segundos, hasta 10 minutos."""
        if time.monotonic() - self.inicio_espera > ESPERA_MAXIMA_S:
            self.timer.stop()
            self.ind_espera.mostrar("Sin confirmación todavía.")
            self.aviso.mostrar("No recibimos la confirmación en 10 minutos. Si ya pagaste, pulsa «Ya pagué, "
                               "verificar» más tarde o escríbenos con tu referencia.", "advertencia")
            return
        self._consultar()

    def _consultar(self) -> None:
        if not self.referencia:
            return
        self.verificar.setEnabled(False)
        ejecutar(self.e.api.estado_pago, self.referencia, al_ok=self._estado,
                 al_error=lambda err: None, al_final=lambda: self.verificar.setEnabled(True), contexto=self)

    def _estado(self, r: dict) -> None:
        estado_pago = r.get("estado")
        if estado_pago == "pendiente":
            return
        self._detener()
        if estado_pago == "aprobado":
            self.e.poner_suscripcion(r.get("suscripcion"))
            self.aviso.mostrar("Plan activado. ¡Gracias! Ya puedes generar tus informes.", "exito")
            self.ventana.recargar_suscripcion()
        else:
            self.aviso.mostrar(r.get("mensaje") or "El pago no se completó. Puedes intentarlo de nuevo.", "error")

    def _detener(self) -> None:
        self.timer.stop()
        self.espera.hide()
