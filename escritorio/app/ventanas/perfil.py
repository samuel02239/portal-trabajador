"""Perfil y suscripción: datos personales, contrato, plantilla, plan, pagos, apariencia y cuenta."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QButtonGroup, QDialog, QDialogButtonBox, QFileDialog, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QRadioButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

from app import tema
from app.estado import estado
from app.servicios.hilos import ejecutar
from app.ventanas.login import mostrar_aviso_datos
from app.widgets import boton, dialogos
from app.widgets.aviso import Aviso
from app.widgets.campos import CampoTexto
from app.widgets.carga import Indicador
from app.widgets.medidor_cupo import texto_cupo
from app.widgets.tarjeta import PaginaDesplazable, Tarjeta

ESTADOS_PAGO = {"pendiente": "Pendiente", "aprobado": "Aprobado", "rechazado": "Rechazado", "anulado": "Anulado",
                "error": "Error"}


class DialogoPlantilla(QDialog):
    """Muestra el mapa de campos detectado para que el usuario lo confirme una sola vez."""

    def __init__(self, padre, respuesta: dict):
        super().__init__(padre)
        self.setWindowTitle("Confirmar plantilla")
        self.setMinimumWidth(620)
        c = QVBoxLayout(self)
        t = QLabel("Revisa dónde escribiremos cada dato en tu plantilla:")
        t.setProperty("rol", "seccion")
        c.addWidget(t)
        tabla = QTableWidget(len(respuesta["resumen"]), 3)
        tabla.setHorizontalHeaderLabels(["", "Dato", "Ubicación en la plantilla"])
        tabla.verticalHeader().hide()
        tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        for i, f in enumerate(respuesta["resumen"]):
            tabla.setItem(i, 0, QTableWidgetItem("Sí" if f["ok"] else "No"))
            tabla.setItem(i, 1, QTableWidgetItem(f["nombre"]))
            tabla.setItem(i, 2, QTableWidgetItem(f["ubicacion"]))
        tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        tabla.resizeColumnsToContents()
        tabla.setMinimumHeight(360)
        c.addWidget(tabla)
        if respuesta.get("faltantes"):
            c.addWidget(Aviso("Faltan datos obligatorios: " + ", ".join(respuesta["faltantes"]) +
                              ". Si la tabla de obligaciones no aparece, no se puede usar esta plantilla.",
                              "advertencia"))
        botones = QDialogButtonBox()
        ok = botones.addButton("Confirmar y usar esta plantilla", QDialogButtonBox.AcceptRole)
        ok.setProperty("variante", "primario")
        ok.setEnabled("ejecucion" not in (respuesta.get("faltantes") or []))
        botones.addButton("Cancelar", QDialogButtonBox.RejectRole)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        c.addWidget(botones)


class VentanaPerfil(PaginaDesplazable):
    def __init__(self, ventana):
        super().__init__()
        self.ventana = ventana
        self.e = estado()
        self.plantilla: dict | None = None
        c = self.capa
        titulo = QLabel("Perfil y suscripción")
        titulo.setProperty("rol", "titulo")
        c.addWidget(titulo)
        self.aviso = Aviso(cerrable=True)
        c.addWidget(self.aviso)

        # Datos personales
        t1 = Tarjeta("Tus datos")
        g = QGridLayout()
        self.nombre = CampoTexto("Nombre completo")
        self.cedula = CampoTexto("Número de cédula", ayuda="Vinculada a tu cuenta desde tu contrato; no se puede "
                                                          "cambiar. Cada persona tiene una sola cuenta.")
        self.cedula.campo.setReadOnly(True)
        self.correo = CampoTexto("Correo")
        self.correo.campo.setReadOnly(True)
        g.addWidget(self.nombre, 0, 0)
        g.addWidget(self.cedula, 0, 1)
        g.addWidget(self.correo, 1, 0)
        t1.capa.addLayout(g)
        guardar = boton("Guardar mis datos", "primario")
        guardar.clicked.connect(self._guardar_datos)
        t1.capa.addWidget(guardar, 0, Qt.AlignRight)
        c.addWidget(t1)

        # Contrato
        t2 = Tarjeta("Contrato")
        self.resumen_contrato = QLabel()
        self.resumen_contrato.setWordWrap(True)
        t2.agregar(self.resumen_contrato)
        f2 = QHBoxLayout()
        editar = boton("Editar datos del contrato")
        editar.clicked.connect(lambda: self.ventana.mostrar_revisar(editar=True))
        nuevo = boton("Cargar un contrato nuevo")
        nuevo.clicked.connect(self._contrato_nuevo)
        f2.addWidget(editar)
        f2.addWidget(nuevo)
        f2.addStretch(1)
        t2.capa.addLayout(f2)
        c.addWidget(t2)

        # Plantilla
        t3 = Tarjeta("Plantilla del informe")
        self.texto_plantilla = QLabel()
        self.texto_plantilla.setWordWrap(True)
        t3.agregar(self.texto_plantilla)
        self.ind_plantilla = Indicador()
        t3.agregar(self.ind_plantilla)
        f3 = QHBoxLayout()
        propia = boton("Usar mi propia plantilla (.docx)")
        propia.clicked.connect(self._subir_plantilla)
        self.oficial = boton("Volver a la plantilla oficial", "enlace")
        self.oficial.clicked.connect(self._quitar_plantilla)
        f3.addWidget(propia)
        f3.addWidget(self.oficial)
        f3.addStretch(1)
        t3.capa.addLayout(f3)
        c.addWidget(t3)

        # Suscripción y pagos
        t4 = Tarjeta("Suscripción")
        self.texto_plan = QLabel()
        self.texto_plan.setWordWrap(True)
        t4.agregar(self.texto_plan)
        ver = boton("Ver planes")
        ver.clicked.connect(lambda: self.ventana.ir("planes"))
        t4.agregar(ver)
        hist = QLabel("Historial de pagos")
        hist.setProperty("rol", "seccion")
        t4.agregar(hist)
        self.pagos = QTableWidget(0, 4)
        self.pagos.setHorizontalHeaderLabels(["Fecha", "Plan", "Valor", "Estado"])
        self.pagos.verticalHeader().hide()
        self.pagos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pagos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pagos.setMaximumHeight(180)
        self.pagos.setAccessibleName("Historial de pagos")
        t4.agregar(self.pagos)
        c.addWidget(t4)

        # Apariencia
        t5 = Tarjeta("Apariencia")
        f5 = QHBoxLayout()
        self.grupo_tema = QButtonGroup(self)
        for clave, texto in (("sistema", "Como Windows"), ("claro", "Claro"), ("oscuro", "Oscuro")):
            r = QRadioButton(texto)
            r.setProperty("clave", clave)
            self.grupo_tema.addButton(r)
            f5.addWidget(r)
            if clave == self.e.modo_tema():
                r.setChecked(True)
        f5.addStretch(1)
        self.grupo_tema.buttonClicked.connect(self._cambiar_tema)
        t5.capa.addLayout(f5)
        c.addWidget(t5)

        # Privacidad y cuenta
        t6 = Tarjeta("Privacidad y cuenta")
        texto = QLabel("Tus datos se usan solo para preparar tus informes (Ley 1581 de 2012). Puedes eliminar tu "
                       "cuenta con todos tus archivos cuando quieras.")
        texto.setWordWrap(True)
        t6.agregar(texto)
        f6 = QHBoxLayout()
        leer = boton("Ver aviso de tratamiento de datos", "enlace")
        leer.clicked.connect(lambda: mostrar_aviso_datos(self))
        salir = boton("Cerrar sesión")
        salir.clicked.connect(lambda: self.ventana.cerrar_sesion())
        eliminar = boton("Eliminar mi cuenta", "peligro")
        eliminar.clicked.connect(self._eliminar_cuenta)
        f6.addWidget(leer)
        f6.addStretch(1)
        f6.addWidget(salir)
        f6.addWidget(eliminar)
        t6.capa.addLayout(f6)
        self.ind_cuenta = Indicador()
        t6.agregar(self.ind_cuenta)
        c.addWidget(t6)

        self.e.suscripcion_cambiada.connect(self._pintar_plan)
        self.e.contrato_cambiado.connect(self._pintar_contrato)

    # ------------------------------------------------------------------
    def al_mostrar(self, mensaje: str | None = None, **_) -> None:
        if mensaje:
            self.aviso.mostrar(mensaje, "exito")
        p = self.e.perfil
        self.nombre.poner(p.get("nombre_completo"))
        self.cedula.poner(p.get("cedula"))
        self.correo.poner(p.get("email") or (self.e.sesion.email if self.e.sesion else ""))
        self._pintar_contrato()
        self._pintar_plan()

        def cargar():
            token = self.e.gestor.token()
            return self.e.auth.pagos(token), self.e.api.plantilla_actual()

        ejecutar(cargar, al_ok=self._cargado, al_error=lambda err: self.ventana.manejar_error(err, self.aviso),
                 contexto=self)

    def _cargado(self, r) -> None:
        pagos, plantilla = r
        self.pagos.setRowCount(len(pagos))
        for i, p in enumerate(pagos):
            valores = [p["created_at"][:10], p["plan_id"].capitalize(), f"${p['monto_cop']:,.0f}".replace(",", "."),
                       ESTADOS_PAGO.get(p["estado"], p["estado"])]
            for j, v in enumerate(valores):
                self.pagos.setItem(i, j, QTableWidgetItem(v))
        self._pintar_plantilla(plantilla)

    def _pintar_contrato(self) -> None:
        c = self.e.contrato or {}
        if not c:
            self.resumen_contrato.setText("No tienes un contrato activo.")
            return
        especificas = len(self.e.especificas())
        f = lambda iso: f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else "sin fecha"  # noqa: E731
        lineas = [f"<b>Contrato {c.get('numero_contrato') or 'sin número'}</b> · {c.get('dependencia') or ''}",
                  f"Del {f(c.get('fecha_inicio'))} al {f(c.get('fecha_fin'))} · {especificas} obligaciones específicas",
                  f"Supervisor: {c.get('supervisor_nombre') or 'sin nombre'} – {c.get('supervisor_cargo') or ''}"]
        self.resumen_contrato.setText("<br>".join(lineas))

    def _pintar_plan(self) -> None:
        s = self.e.suscripcion
        if not s:
            self.texto_plan.setText("Cargando…")
            return
        fin = s.get("fin") or ""
        vence = f" · vence el {fin[8:10]}/{fin[5:7]}/{fin[:4]}" if fin else ""
        usados = f" · usados {s['usados']}" + (" este mes" if s.get("periodo_limite") == "mensual" else "")
        self.texto_plan.setText(texto_cupo(s) + usados + vence)

    def _pintar_plantilla(self, r: dict) -> None:
        self.plantilla = r.get("plantilla")
        if not self.plantilla:
            self.texto_plantilla.setText("No hay una plantilla configurada.")
            self.oficial.hide()
            return
        if self.plantilla["alcance"] == "global":
            self.texto_plantilla.setText(f"Usas la plantilla oficial ({self.plantilla['nombre']}).")
            self.oficial.hide()
        else:
            self.texto_plantilla.setText(f"Usas tu propia plantilla ({self.plantilla['nombre']}).")
            self.oficial.show()

    # -------------------------------------------------------------- acciones
    def _guardar_datos(self) -> None:
        nombre = self.nombre.texto()
        if len(nombre) < 5:
            self.nombre.error("Escribe tu nombre completo.")
            return

        def guardar():
            token = self.e.gestor.token()
            return self.e.auth.actualizar_perfil(token, self.e.sesion.user_id, nombre)

        ejecutar(guardar, al_ok=self._datos_guardados, al_error=lambda err: self.ventana.manejar_error(err, self.aviso),
                 contexto=self)

    def _datos_guardados(self, perfil: dict) -> None:
        self.e.perfil.update(perfil or {})
        self.e.perfil_cambiado.emit()
        self.e.actividades_cambiadas.emit()  # las alertas de nombre y cédula se recalculan
        self.aviso.mostrar("Guardamos tus datos.", "exito")

    def _contrato_nuevo(self) -> None:
        if dialogos.confirmar(self, "Cargar un contrato nuevo",
                              "Tu contrato actual quedará inactivo cuando guardes el nuevo. Los informes que ya "
                              "generaste se conservan. ¿Continuar?", "Continuar"):
            self.ventana.mostrar_minuta(reemplazo=True)

    def _subir_plantilla(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Elegir plantilla en blanco", "", "Word (*.docx)")
        if not ruta:
            return
        self.ind_plantilla.mostrar("Analizando la plantilla…")
        ejecutar(self.e.api.subir_plantilla, ruta, al_ok=self._plantilla_subida,
                 al_error=lambda err: self.ventana.manejar_error(err, self.aviso),
                 al_final=self.ind_plantilla.ocultar, contexto=self)

    def _plantilla_subida(self, r: dict) -> None:
        if DialogoPlantilla(self, r).exec() != QDialog.Accepted:
            return
        ejecutar(self.e.api.confirmar_plantilla, r["plantilla"]["id"], r.get("mapa_campos"),
                 al_ok=lambda x: (self._pintar_plantilla(x), self.aviso.mostrar("Tus próximos informes usarán tu plantilla.", "exito")),
                 al_error=lambda err: self.ventana.manejar_error(err, self.aviso), contexto=self)

    def _quitar_plantilla(self) -> None:
        if not self.plantilla or self.plantilla["alcance"] != "usuario":
            return
        ejecutar(self.e.api.quitar_plantilla, self.plantilla["id"],
                 al_ok=lambda x: (self._pintar_plantilla(x), self.aviso.mostrar("Volviste a la plantilla oficial.", "exito")),
                 al_error=lambda err: self.ventana.manejar_error(err, self.aviso), contexto=self)

    def _cambiar_tema(self, boton_radio) -> None:
        modo = boton_radio.property("clave")
        self.e.guardar_modo_tema(modo)
        tema.aplicar(QApplication.instance(), modo)

    def _eliminar_cuenta(self) -> None:
        if not dialogos.confirmar(self, "Eliminar mi cuenta",
                                  "Se borrarán tu cuenta, tu contrato, tus actividades, tus informes y todos tus "
                                  "archivos. No se puede deshacer.", "Continuar", peligro=True):
            return
        texto = dialogos.pedir_texto(self, "Confirmar eliminación", "Escribe ELIMINAR para confirmar:")
        if texto != "ELIMINAR":
            return
        self.ind_cuenta.mostrar("Eliminando tu cuenta…")
        ejecutar(self.e.api.eliminar_cuenta, al_ok=self._cuenta_eliminada,
                 al_error=lambda err: self.ventana.manejar_error(err, self.aviso),
                 al_final=self.ind_cuenta.ocultar, contexto=self)

    def _cuenta_eliminada(self, _) -> None:
        self.e.gestor.establecer(None)
        self.ventana.mostrar_login("Eliminamos tu cuenta y todos tus datos.", "info")
