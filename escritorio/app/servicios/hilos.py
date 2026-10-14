"""Tareas en segundo plano (QThreadPool) para que la ventana nunca se congele.

Uso:
    ejecutar(api.contrato_actual, al_ok=self._mostrar, al_error=self._error, contexto=self)

Los resultados llegan al hilo de la interfaz. Si el widget 'contexto' ya fue
destruido cuando termina la tarea, el resultado se descarta sin errores.
"""
from __future__ import annotations

import logging
import traceback
from typing import Any, Callable

import shiboken6
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

log = logging.getLogger("portal.hilos")


class _Senales(QObject):
    ok = Signal(object)
    error = Signal(object)


class _Receptor(QObject):
    """Vive en el hilo de la interfaz y entrega los resultados a los callbacks."""

    def __init__(self, al_ok, al_error, al_final, contexto):
        super().__init__()
        self._al_ok, self._al_error, self._al_final, self._contexto = al_ok, al_error, al_final, contexto

    def _vivo(self) -> bool:
        return self._contexto is None or shiboken6.isValid(self._contexto)

    @Slot(object)
    def recibir_ok(self, resultado):
        try:
            if self._vivo() and self._al_ok:
                self._al_ok(resultado)
        finally:
            self._terminar()

    @Slot(object)
    def recibir_error(self, error):
        try:
            if self._vivo():
                if self._al_error:
                    self._al_error(error)
                else:
                    log.error("Error en tarea sin manejador: %r", error)
        finally:
            self._terminar()

    def _terminar(self):
        try:
            if self._vivo() and self._al_final:
                self._al_final()
        finally:
            _vivos.discard(self)


class _Tarea(QRunnable):
    def __init__(self, fn: Callable, args, kwargs, senales: _Senales):
        super().__init__()
        self.fn, self.args, self.kwargs, self.senales = fn, args, kwargs, senales

    def run(self):
        try:
            resultado = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # se entrega a la interfaz
            if not getattr(exc, "esperado", False):
                log.debug("Tarea falló:\n%s", traceback.format_exc())
            self.senales.error.emit(exc)
        else:
            self.senales.ok.emit(resultado)


_vivos: set[_Receptor] = set()


def ejecutar(fn: Callable, *args: Any, al_ok: Callable | None = None, al_error: Callable | None = None,
             al_final: Callable | None = None, contexto: QObject | None = None, **kwargs: Any) -> None:
    receptor = _Receptor(al_ok, al_error, al_final, contexto)
    senales = _Senales()
    senales.ok.connect(receptor.recibir_ok)
    senales.error.connect(receptor.recibir_error)
    receptor._senales = senales  # mantiene vivo el emisor mientras dura la tarea
    _vivos.add(receptor)
    QThreadPool.globalInstance().start(_Tarea(fn, args, kwargs, senales))
