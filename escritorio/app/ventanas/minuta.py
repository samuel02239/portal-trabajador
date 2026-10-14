"""Subir minuta (primer ingreso o cambio de contrato)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.estado import estado
from app.servicios.hilos import ejecutar
from app.widgets import boton
from app.widgets.aviso import Aviso
from app.widgets.carga import Indicador
from app.widgets.tarjeta import PaginaDividida, PanelMarca
from app.widgets.zona_archivo import ZonaArchivo


class VentanaMinuta(PaginaDividida):
    def __init__(self, ventana):
        super().__init__(PanelMarca(
            "Configura tu contrato una sola vez.",
            "Con la minuta sabemos tus obligaciones, tus fechas y tu supervisor. Así cada actividad queda en su lugar.",
            [("fa6s.file-arrow-up", "1. Sube la minuta de tu contrato en PDF o Word."),
             ("fa6s.list-check", "2. Revisa los datos y las obligaciones que encontramos."),
             ("fa6s.pen-to-square", "3. Empieza a registrar tus actividades.")]), 440)
        self.ventana = ventana
        self.e = estado()
        self.reemplazo = False
        c = self.capa
        c.setSpacing(14)
        etapa = QLabel("PASO 1 DE 2")
        etapa.setProperty("rol", "secundario")
        etapa.setStyleSheet("font-weight: 600; letter-spacing: 1px;")
        c.addWidget(etapa)
        paso = QLabel("Sube tu minuta")
        paso.setProperty("rol", "titulo")
        explicacion = QLabel("Sube la minuta de tu contrato. Leeremos tus datos y tus obligaciones, y luego "
                             "podrás revisarlos y corregirlos antes de guardar.")
        explicacion.setWordWrap(True)
        explicacion.setProperty("rol", "secundario")
        self.zona = ZonaArchivo("Arrastra tu minuta (PDF o Word)")
        self.aviso = Aviso()
        self.indicador = Indicador()
        self.leer = boton("Leer mi contrato", "primario")
        self.leer.setEnabled(False)
        self.cancelar = boton("Cerrar sesión", "enlace")
        for w in (paso, explicacion, self.zona, self.aviso, self.indicador, self.leer):
            c.addWidget(w)
        c.addWidget(self.cancelar, 0, Qt.AlignLeft)

        self.zona.archivo_elegido.connect(self._elegido)
        self.zona.archivo_invalido.connect(lambda m: self.aviso.mostrar(m, "error"))
        self.leer.clicked.connect(self._leer)
        self.cancelar.clicked.connect(self._cancelar)

    def preparar(self, reemplazo: bool = False) -> None:
        self.reemplazo = reemplazo
        self.cancelar.setText("Cancelar y volver" if reemplazo else "Cerrar sesión")
        self.aviso.ocultar()
        self.indicador.ocultar()
        self.leer.setEnabled(bool(self.zona.ruta))

    def _elegido(self, _ruta: str) -> None:
        self.aviso.ocultar()
        self.leer.setEnabled(True)
        self.leer.setFocus()

    def _leer(self) -> None:
        if not self.zona.ruta:
            return
        self.leer.setEnabled(False)
        self.zona.setEnabled(False)
        self.aviso.ocultar()
        self.indicador.mostrar("Leyendo tu contrato… puede tardar hasta un minuto.")
        ejecutar(self.e.api.leer_minuta, self.zona.ruta, al_ok=self._leido, al_error=self._error,
                 al_final=self._fin, contexto=self)

    def _fin(self) -> None:
        self.indicador.ocultar()
        self.zona.setEnabled(True)
        self.leer.setEnabled(True)

    def _leido(self, lectura: dict) -> None:
        self.ventana.mostrar_revisar(lectura=lectura, reemplazo=self.reemplazo)

    def _error(self, err) -> None:
        self.ventana.manejar_error(err, self.aviso)

    def _cancelar(self) -> None:
        if self.reemplazo:
            self.ventana.ir("perfil")
        else:
            self.ventana.cerrar_sesion()
