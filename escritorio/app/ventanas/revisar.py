"""Revisar datos extraídos de la minuta (o editar el contrato guardado).

Formulario con cada dato del contrato editable y la lista de obligaciones
numeradas (editar, eliminar, agregar). Nada se guarda hasta confirmar.
"""
from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from app.estado import estado
from app.servicios.hilos import ejecutar
from app.widgets import boton, dialogos, icono, mostrar_en
from app.widgets.aviso import Aviso
from app.widgets.campos import AreaTexto, CampoFecha, CampoOpciones, CampoTexto
from app.widgets.carga import Indicador
from app.widgets.tarjeta import PaginaDesplazable, Tarjeta

TIPOS = [("Prestación de servicios", "prestacion_servicios"), ("Práctica formativa", "practica_formativa"),
         ("Otro", "otro")]


def formato_pesos(valor) -> str:
    if valor in (None, ""):
        return ""
    try:
        return f"{int(round(float(valor))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(valor)


def leer_pesos(texto: str) -> float | None:
    digitos = re.sub(r"[^\d]", "", texto or "")
    return float(digitos) if digitos else None


class _FilaObligacion(QWidget):
    eliminar = Signal(object)

    def __init__(self, texto: str = "", id_: str | None = None, claves: list | None = None):
        super().__init__()
        self.id = id_
        self.claves = claves or []
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        self.numero = QLabel()
        self.numero.setProperty("rol", "seccion")
        self.numero.setFixedWidth(28)
        self.numero.setAlignment(Qt.AlignTop | Qt.AlignRight)
        self.texto = QPlainTextEdit(texto)
        self.texto.setFixedHeight(76)
        self.texto.setTabChangesFocus(True)
        quitar = QPushButton(icono("fa6s.trash"), "")
        quitar.setToolTip("Eliminar esta obligación")
        quitar.setAccessibleName("Eliminar obligación")
        quitar.setProperty("variante", "icono")
        quitar.clicked.connect(lambda: self.eliminar.emit(self))
        fila.addWidget(self.numero)
        fila.addWidget(self.texto, 1)
        fila.addWidget(quitar, 0, Qt.AlignTop)

    def poner_numero(self, n: int) -> None:
        self.numero.setText(f"{n}.")
        self.texto.setAccessibleName(f"Obligación {n}")


class ListaObligaciones(QWidget):
    def __init__(self, tipo: str):
        super().__init__()
        self.tipo = tipo
        capa = QVBoxLayout(self)
        capa.setContentsMargins(0, 0, 0, 0)
        self.filas_capa = QVBoxLayout()
        self.filas_capa.setSpacing(8)
        capa.addLayout(self.filas_capa)
        agregar = boton("Agregar obligación", "secundario", icono("fa6s.plus"))
        agregar.clicked.connect(lambda: self.agregar("", foco=True))
        capa.addWidget(agregar, 0, Qt.AlignLeft)
        self.filas: list[_FilaObligacion] = []

    def poner(self, obligaciones: list[dict]) -> None:
        for f in self.filas:
            f.deleteLater()
        self.filas = []
        for o in sorted(obligaciones, key=lambda x: x.get("numero") or 0):
            self.agregar(o.get("texto", ""), o.get("id"), o.get("palabras_clave"))

    def agregar(self, texto: str = "", id_=None, claves=None, foco: bool = False) -> None:
        f = _FilaObligacion(texto, id_, claves)
        f.eliminar.connect(self._quitar)
        self.filas.append(f)
        mostrar_en(self.filas_capa, f)
        self._numerar()
        if foco:
            f.texto.setFocus()

    def _quitar(self, fila) -> None:
        if fila.texto.toPlainText().strip() and not dialogos.confirmar(
                self, "Eliminar obligación", "¿Eliminar esta obligación de la lista?", "Eliminar", peligro=True):
            return
        self.filas.remove(fila)
        fila.deleteLater()
        self._numerar()

    def _numerar(self) -> None:
        for i, f in enumerate(self.filas, 1):
            f.poner_numero(i)

    def valores(self) -> list[dict]:
        salida = []
        for f in self.filas:
            texto = re.sub(r"\s+", " ", f.texto.toPlainText()).strip()
            if texto:
                d = {"numero": len(salida) + 1, "tipo": self.tipo, "texto": texto, "palabras_clave": f.claves}
                if f.id:
                    d["id"] = f.id
                salida.append(d)
        return salida


class VentanaRevisar(PaginaDesplazable):
    def __init__(self, ventana):
        super().__init__(ancho_max=940)
        self.setObjectName("fondo")
        self.ventana = ventana
        self.e = estado()
        self.lectura: dict | None = None
        self.editar = False
        c = self.capa

        self.titulo = QLabel("Paso 2 de 2 · Revisa tus datos")
        self.titulo.setProperty("rol", "titulo")
        self.subtitulo = QLabel("Corrige lo que haga falta. Estos datos se usan para llenar tu informe.")
        self.subtitulo.setProperty("rol", "secundario")
        self.subtitulo.setWordWrap(True)
        c.addWidget(self.titulo)
        c.addWidget(self.subtitulo)
        self.avisos = QVBoxLayout()
        c.addLayout(self.avisos)

        t1 = Tarjeta("Tus datos")
        g1 = QGridLayout()
        self.nombre = CampoTexto("Nombre completo *")
        self.cedula = CampoTexto("Número de cédula *", ayuda="Debe ser la que aparece en la minuta. Queda vinculada "
                                                            "a tu cuenta: cada persona tiene una sola cuenta.")
        g1.addWidget(self.nombre, 0, 0)
        g1.addWidget(self.cedula, 0, 1)
        t1.capa.addLayout(g1)
        c.addWidget(t1)

        t2 = Tarjeta("Contrato")
        g2 = QGridLayout()
        g2.setHorizontalSpacing(16)
        self.numero = CampoTexto("Número del contrato")
        self.tipo = CampoOpciones("Tipo de contratación", TIPOS)
        self.entidad = CampoTexto("Entidad")
        self.dependencia = CampoTexto("Dependencia donde presta el servicio")
        self.proyecto = CampoTexto("Proyecto o programa (si aplica)")
        self.fecha_contrato = CampoFecha("Fecha del contrato (suscripción)")
        self.fecha_inicio = CampoFecha("Fecha de inicio")
        self.fecha_fin = CampoFecha("Fecha de terminación")
        self.valor = CampoTexto("Valor total (pesos)")
        self.plazo = CampoTexto("Plazo")
        g2.addWidget(self.numero, 0, 0)
        g2.addWidget(self.tipo, 0, 1)
        g2.addWidget(self.entidad, 1, 0)
        g2.addWidget(self.dependencia, 1, 1)
        g2.addWidget(self.proyecto, 2, 0)
        g2.addWidget(self.fecha_contrato, 2, 1)
        g2.addWidget(self.fecha_inicio, 3, 0)
        g2.addWidget(self.fecha_fin, 3, 1)
        g2.addWidget(self.valor, 4, 0)
        g2.addWidget(self.plazo, 4, 1)
        t2.capa.addLayout(g2)
        self.objeto = AreaTexto("Objeto del contrato", maximo=3000, alto=80)
        self.forma_pago = AreaTexto("Forma de pago", maximo=2000, alto=60)
        t2.agregar(self.objeto)
        t2.agregar(self.forma_pago)
        c.addWidget(t2)

        t3 = Tarjeta("Supervisor")
        g3 = QGridLayout()
        self.sup_nombre = CampoTexto("Nombre del supervisor")
        self.sup_cargo = CampoTexto("Cargo del supervisor")
        g3.addWidget(self.sup_nombre, 0, 0)
        g3.addWidget(self.sup_cargo, 0, 1)
        t3.capa.addLayout(g3)
        c.addWidget(t3)

        t4 = Tarjeta("Obligaciones específicas *", "Son las que aparecen en el informe. Revisa que estén completas "
                                                   "y en orden.")
        self.especificas = ListaObligaciones("especifica")
        t4.agregar(self.especificas)
        c.addWidget(t4)
        t5 = Tarjeta("Obligaciones generales", "Se guardan como referencia; no van en la tabla del informe.")
        self.generales = ListaObligaciones("general")
        t5.agregar(self.generales)
        c.addWidget(t5)

        self.aviso = Aviso()
        c.addWidget(self.aviso)
        self.indicador = Indicador("Guardando…")
        c.addWidget(self.indicador)
        botones = QHBoxLayout()
        self.volver = boton("Volver a subir la minuta", "secundario")
        self.guardar = boton("Confirmar y entrar", "primario")
        self.volver.clicked.connect(self._volver)
        self.guardar.clicked.connect(self._guardar)
        botones.addWidget(self.volver)
        botones.addStretch(1)
        botones.addWidget(self.guardar)
        c.addLayout(botones)

    # ------------------------------------------------------------------
    def preparar(self, lectura: dict | None = None, editar: bool = False, reemplazo: bool = False) -> None:
        self.lectura, self.editar = lectura, editar
        self.aviso.ocultar()
        self.indicador.ocultar()
        self.guardar.setEnabled(True)
        while self.avisos.count():
            w = self.avisos.takeAt(0).widget()
            if w:
                w.deleteLater()
        if editar:
            self.titulo.setText("Editar datos del contrato")
            self.subtitulo.setText("Los cambios se usan en los próximos informes que generes.")
            self.guardar.setText("Guardar cambios")
            self.volver.setText("Cancelar")
            c, p = self.e.contrato or {}, self.e.perfil
            self._llenar(c, p.get("nombre_completo"), p.get("cedula"), self.e.obligaciones)
        else:
            self.titulo.setText("Paso 2 de 2 · Revisa tus datos")
            self.subtitulo.setText("Corrige lo que haga falta. Estos datos se usan para llenar tu informe.")
            self.guardar.setText("Confirmar y guardar" if reemplazo else "Confirmar y entrar")
            self.volver.setText("Volver a subir la minuta")
            d = (lectura or {}).get("datos") or {}
            ct, sup, con = d.get("contrato") or {}, d.get("supervisor") or {}, d.get("contratista") or {}
            plano = {**ct, "numero_contrato": ct.get("numero"), "supervisor_nombre": sup.get("nombre"),
                     "supervisor_cargo": sup.get("cargo")}
            self._llenar(plano, con.get("nombre") or self.e.perfil.get("nombre_completo"),
                         con.get("cedula") or self.e.perfil.get("cedula"), d.get("obligaciones") or [])
            for texto in (lectura or {}).get("avisos") or []:
                mostrar_en(self.avisos, Aviso(texto, "advertencia"))
            if (lectura or {}).get("modelo"):
                mostrar_en(self.avisos, Aviso(f"Datos leídos con IA ({lectura['modelo']}). Revísalos antes de guardar.",
                                              "info"))
        # Una cédula ya vinculada a la cuenta no se puede cambiar
        vinculada = re.sub(r"\D", "", self.e.perfil.get("cedula") or "")
        if vinculada:
            self.cedula.poner(vinculada)
        self.cedula.campo.setReadOnly(bool(vinculada))
        self.cedula.campo.setToolTip("Vinculada a tu cuenta; no se puede cambiar." if vinculada else "")
        self.nombre.campo.setFocus()

    def _llenar(self, c: dict, nombre, cedula, obligaciones: list[dict]) -> None:
        self.nombre.poner(nombre)
        self.cedula.poner(cedula)
        self.numero.poner(c.get("numero_contrato"))
        self.tipo.poner(c.get("tipo_contratacion") or "prestacion_servicios")
        self.entidad.poner(c.get("entidad"))
        self.dependencia.poner(c.get("dependencia"))
        self.proyecto.poner(c.get("proyecto"))
        self.fecha_contrato.poner(c.get("fecha_contrato"))
        self.fecha_inicio.poner(c.get("fecha_inicio"))
        self.fecha_fin.poner(c.get("fecha_fin"))
        self.valor.poner(formato_pesos(c.get("valor_total")))
        self.plazo.poner(c.get("plazo_texto"))
        self.objeto.poner(c.get("objeto"))
        self.forma_pago.poner(c.get("forma_pago"))
        self.sup_nombre.poner(c.get("supervisor_nombre"))
        self.sup_cargo.poner(c.get("supervisor_cargo"))
        self.especificas.poner([o for o in obligaciones if o.get("tipo") == "especifica"])
        self.generales.poner([o for o in obligaciones if o.get("tipo") == "general"])

    def _validar(self) -> bool:
        ok = True
        if len(self.nombre.texto()) < 5:
            self.nombre.error("Escribe tu nombre completo: aparece en el informe.")
            ok = False
        if not re.sub(r"\D", "", self.cedula.texto()):
            self.cedula.error("Escribe tu número de cédula: aparece en el informe.")
            ok = False
        fi, ff = self.fecha_inicio.fecha(), self.fecha_fin.fecha()
        if fi and ff and ff < fi:
            self.fecha_fin.error("La fecha de terminación no puede ser anterior a la de inicio.")
            ok = False
        if not self.especificas.valores():
            self.aviso.mostrar("Agrega al menos una obligación específica.", "error")
            ok = False
        if not ok and not self.aviso.isVisible():
            self.aviso.mostrar("Revisa los campos marcados.", "error")
        return ok

    def _datos(self) -> dict:
        return {
            "contrato": {
                "numero_contrato": self.numero.texto() or None, "entidad": self.entidad.texto() or None,
                "tipo_contratacion": self.tipo.valor(), "proyecto": self.proyecto.texto() or None,
                "objeto": self.objeto.texto() or None, "dependencia": self.dependencia.texto() or None,
                "supervisor_nombre": self.sup_nombre.texto() or None, "supervisor_cargo": self.sup_cargo.texto() or None,
                "fecha_contrato": self.fecha_contrato.iso(), "fecha_inicio": self.fecha_inicio.iso(),
                "fecha_fin": self.fecha_fin.iso(), "plazo_texto": self.plazo.texto() or None,
                "valor_total": leer_pesos(self.valor.texto()), "forma_pago": self.forma_pago.texto() or None,
            },
            "contratista": {"nombre": self.nombre.texto(), "cedula": re.sub(r"\D", "", self.cedula.texto())},
            "obligaciones": self.especificas.valores() + self.generales.valores(),
        }

    def _guardar(self) -> None:
        self.aviso.ocultar()
        if not self._validar():
            return
        datos = self._datos()
        self.guardar.setEnabled(False)
        self.indicador.mostrar("Guardando…")
        if self.editar:
            ejecutar(self.e.api.editar_contrato, self.e.contrato["id"], datos, al_ok=self._guardado,
                     al_error=self._error, contexto=self)
        else:
            lectura = self.lectura or {}
            datos["lectura_id"] = lectura.get("lectura_id")
            ejecutar(self.e.api.guardar_contrato, datos, al_ok=self._guardado, al_error=self._error, contexto=self)

    def _guardado(self, respuesta: dict) -> None:
        self.indicador.ocultar()
        self.guardar.setEnabled(True)
        d = self._datos()["contratista"]
        self.e.perfil.update(nombre_completo=d["nombre"], cedula=d["cedula"])
        self.e.perfil_cambiado.emit()
        self.e.poner_contrato(respuesta)
        self.e.periodo = None
        self.ventana.recargar_suscripcion()
        if self.editar:
            self.ventana.ir("perfil", mensaje="Guardamos los cambios del contrato.")
        else:
            self.ventana.ir("inicio")

    def _error(self, err) -> None:
        self.indicador.ocultar()
        self.guardar.setEnabled(True)
        codigo = getattr(err, "codigo", "")
        if codigo in ("cedula_en_uso", "cedula_distinta", "cedula_no_en_minuta", "cedula_invalida"):
            self.cedula.error(str(err))
            self.cedula.campo.setFocus()
        if codigo == "lectura_invalida":
            self.aviso.mostrar(str(err), "error", accion="Volver a subir la minuta")
            try:
                self.aviso.accion.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.aviso.accion.connect(self._volver)
            return
        self.ventana.manejar_error(err, self.aviso)

    def _volver(self) -> None:
        if self.editar:
            self.ventana.ir("perfil")
        else:
            self.ventana.mostrar_minuta(reemplazo=bool(self.e.contrato))
