"""Llamadas a OpenRouter con respaldo en cascada entre modelos (sección 7.1).

Una sola función, llamar_ia(tarea, mensajes, esquema), que todo el código reutiliza:
- Los modelos y su orden salen de providers.json (o de OPENROUTER_MODELS).
- Timeout de 60 s y hasta 2 reintentos por modelo ante errores de red o 429/5xx.
- La respuesta se valida con pydantic; si no valida, se reintenta una vez
  indicándole al modelo el error. Si vuelve a fallar, pasa al siguiente modelo.
- Cada intento queda en ia_logs (solo metadatos, nunca el contenido).
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
from pydantic import BaseModel, ValidationError

from config import cfg, proveedores_ia

log = logging.getLogger("portal.ia")

API_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT = 60
REINTENTOS = 2
TRANSITORIOS = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529}

_logs = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ia_logs")


class IAError(Exception):
    """Todos los modelos fallaron."""


class IANoConfigurada(IAError):
    """Falta la llave o no hay modelos activos."""


class _Transitorio(Exception):
    pass


class _Permanente(Exception):
    pass


class _FalloLlave(Exception):
    """La llave no sirve por ahora (inválida, sin saldo o con límite): se pausa y se usa otra."""

    def __init__(self, mensaje: str, segundos: int):
        super().__init__(mensaje)
        self.segundos = segundos


# Pausas de las llaves: llave -> momento (monotonic) hasta el que no se usa
_PAUSAS: dict[str, float] = {}
_LOCK_LLAVES = threading.Lock()
PAUSA_POR_ESTADO = {401: 3600, 403: 3600, 402: 900, 429: 30}


def _llaves() -> tuple[str, ...]:
    return cfg.openrouter_api_keys


def llave_visible(llave: str) -> str:
    return f"…{llave[-5:]}" if llave else ""


def _pausar(llave: str, segundos: int) -> None:
    with _LOCK_LLAVES:
        _PAUSAS[llave] = time.monotonic() + segundos


def _elegir_llave(excluir: set[str]) -> str | None:
    """Primera llave (en el orden configurado) que no esté en pausa ni ya probada en esta llamada."""
    ahora = time.monotonic()
    with _LOCK_LLAVES:
        for llave in _llaves():
            if llave not in excluir and _PAUSAS.get(llave, 0) <= ahora:
                return llave
    return None


def estado_llaves() -> dict:
    ahora = time.monotonic()
    with _LOCK_LLAVES:
        pausadas = sum(1 for k in _llaves() if _PAUSAS.get(k, 0) > ahora)
    return {"total": len(_llaves()), "disponibles": len(_llaves()) - pausadas}


def ia_configurada() -> bool:
    return bool(_llaves() and proveedores_ia())


def extraer_json(texto: str) -> dict:
    """Saca el objeto JSON de la respuesta (quita <think>, bloques ``` y texto alrededor)."""
    texto = re.sub(r"<think>.*?</think>", "", texto or "", flags=re.S)
    a, b = texto.find("{"), texto.rfind("}")
    if a == -1 or b <= a:
        raise ValueError("la respuesta no contiene un objeto JSON")
    return json.loads(texto[a:b + 1])


def _registrar(user_id, tarea, modelo, ok, t0, tokens_in, tokens_out, error, llave: str = ""):
    fila = {"user_id": user_id, "tarea": tarea, "modelo": modelo, "ok": ok,
            "ms": int((time.monotonic() - t0) * 1000), "tokens_in": tokens_in,
            "tokens_out": tokens_out, "error": (error or None) and str(error)[:500],
            "llave": llave_visible(llave) or None}

    def _guardar():
        try:
            from db import get_db
            get_db().insertar("ia_logs", fila)
        except Exception as exc:  # el log nunca debe tumbar la petición
            log.warning("No se pudo guardar ia_logs: %s", type(exc).__name__)

    _logs.submit(_guardar)


def _post(cliente: httpx.Client, p: dict, mensajes: list[dict], max_tokens: int, temperatura: float, llave: str):
    body = {
        "model": p["model"],
        "messages": mensajes,
        "max_tokens": int(max_tokens) + int(p.get("max_tokens_extra", 0)),
        "temperature": p.get("temperature", temperatura),
    }
    if p.get("reasoning") is not None:
        body["reasoning"] = p["reasoning"]
    if p.get("json_mode"):
        body["response_format"] = {"type": "json_object"}
    headers = {
        "Authorization": f"Bearer {llave}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://portal-trabajador.app",
        "X-Title": "Portal del Trabajador",
    }
    try:
        r = cliente.post(API_URL, json=body, headers=headers, timeout=TIMEOUT)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise _Transitorio(f"red: {type(exc).__name__}") from exc
    if r.status_code in PAUSA_POR_ESTADO:
        raise _FalloLlave(f"HTTP {r.status_code}: {r.text[:120]}", PAUSA_POR_ESTADO[r.status_code])
    if r.status_code in TRANSITORIOS:
        raise _Transitorio(f"HTTP {r.status_code}: {r.text[:150]}")
    if r.status_code >= 400:
        raise _Permanente(f"HTTP {r.status_code}: {r.text[:150]}")
    try:
        d = r.json()
    except ValueError as exc:
        raise _Transitorio("respuesta no es JSON") from exc
    if d.get("error"):  # OpenRouter a veces responde 200 con un error dentro
        codigo = (d["error"] or {}).get("code") if isinstance(d["error"], dict) else None
        if codigo in PAUSA_POR_ESTADO:
            raise _FalloLlave(str(d["error"])[:200], PAUSA_POR_ESTADO[codigo])
        if codigo in TRANSITORIOS:
            raise _Transitorio(str(d["error"])[:200])
        raise _Permanente(str(d["error"])[:200])
    ch = (d.get("choices") or [{}])[0]
    texto = (ch.get("message") or {}).get("content") or ""
    if not texto.strip():
        raise _Permanente(f"respuesta vacía (finish_reason={ch.get('finish_reason')}; "
                          "sube max_tokens_extra en providers.json)")
    u = d.get("usage") or {}
    return texto, u.get("prompt_tokens"), u.get("completion_tokens")


def _resumen_validacion(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}"
                         for e in exc.errors(include_input=False)[:6])
    return str(exc)[:300]


def llamar_ia(tarea: str, mensajes: list[dict], esquema: type[BaseModel], user_id: str | None = None,
              max_tokens: int = 2000, temperatura: float = 0.2):
    """Devuelve (objeto_validado, nombre_del_modelo). Lanza IAError si todos fallan.

    Por cada modelo se usa la primera llave disponible; si la llave falla (inválida, sin saldo o con
    límite), queda en pausa y se repite con la siguiente llave. Si el modelo falla, se pasa al siguiente.
    """
    if not _llaves():
        raise IANoConfigurada("Falta la llave de OpenRouter (OPENROUTER_API_KEYS en las variables del backend).")
    proveedores = proveedores_ia()
    if not proveedores:
        raise IANoConfigurada("No hay modelos activos en backend/providers.json.")

    errores: list[str] = []
    with httpx.Client() as cliente:
        for p in proveedores:
            nombre = p.get("name") or p["model"]
            msgs = list(mensajes)
            corrigio = False
            fallos_red = 0
            probadas: set[str] = set()
            while True:
                llave = _elegir_llave(probadas)
                if llave is None:
                    errores.append(f"{nombre}: ninguna llave de OpenRouter disponible")
                    break
                t0 = time.monotonic()
                texto, tin, tout = None, None, None
                try:
                    texto, tin, tout = _post(cliente, p, msgs, max_tokens, temperatura, llave)
                    objeto = esquema.model_validate(extraer_json(texto))
                    _registrar(user_id, tarea, p["model"], True, t0, tin, tout, None, llave)
                    return objeto, nombre
                except _FalloLlave as exc:
                    _registrar(user_id, tarea, p["model"], False, t0, tin, tout, f"llave: {exc}", llave)
                    log.warning("Llave %s en pausa %ss: %s", llave_visible(llave), exc.segundos, str(exc)[:80])
                    _pausar(llave, exc.segundos)
                    probadas.add(llave)
                    continue
                except _Transitorio as exc:
                    _registrar(user_id, tarea, p["model"], False, t0, tin, tout, exc, llave)
                    fallos_red += 1
                    if fallos_red <= REINTENTOS:
                        time.sleep(1.5 * fallos_red)
                        continue
                    errores.append(f"{nombre}: {exc}")
                    break
                except (ValueError, ValidationError) as exc:  # JSON inválido o fuera del esquema
                    resumen = _resumen_validacion(exc)
                    _registrar(user_id, tarea, p["model"], False, t0, tin, tout, f"validación: {resumen}", llave)
                    if not corrigio and texto:
                        corrigio = True
                        msgs = msgs + [
                            {"role": "assistant", "content": texto[:8000]},
                            {"role": "user", "content": "Tu respuesta no cumple el esquema pedido ("
                                                        f"{resumen}). Corrígela y responde SOLO con el JSON válido."},
                        ]
                        continue
                    errores.append(f"{nombre}: {resumen}")
                    break
                except _Permanente as exc:
                    _registrar(user_id, tarea, p["model"], False, t0, tin, tout, exc, llave)
                    errores.append(f"{nombre}: {exc}")
                    break
    log.warning("IA %s: todos los modelos fallaron -> %s", tarea, " | ".join(errores)[:500])
    raise IAError(" | ".join(errores))
