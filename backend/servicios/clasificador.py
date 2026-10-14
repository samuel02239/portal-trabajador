"""Clasificación de actividades (sección 7.3): ubica la frase del trabajador en
sus obligaciones específicas y la redacta en tono formal."""
from __future__ import annotations

import prompts
from ia import llamar_ia
from schemas import ClasificacionIA

UMBRAL_ALTO = 0.75
UMBRAL_BAJO = 0.45


def nivel(confianza: float | None, sin_coincidencia: bool = False) -> str:
    """'alta' (≥0.75), 'media' (0.45–0.75) o 'baja' (<0.45 o sin coincidencia)."""
    if sin_coincidencia or confianza is None or confianza < UMBRAL_BAJO:
        return "baja"
    return "alta" if confianza >= UMBRAL_ALTO else "media"


def clasificar(frase: str, fecha: str, contrato: dict, obligaciones: list[dict], user_id: str | None = None) -> dict:
    """obligaciones: solo las específicas, con id, numero y texto. Lanza IAError si todos los modelos fallan."""
    mensajes = [
        {"role": "system", "content": prompts.SISTEMA_CLASIFICAR},
        {"role": "user", "content": prompts.usuario_clasificar(frase, fecha, contrato, obligaciones)},
    ]
    resultado, modelo = llamar_ia("clasificar_actividad", mensajes, ClasificacionIA, user_id=user_id,
                                  max_tokens=1200, temperatura=0.2)
    por_numero = {o["numero"]: o for o in obligaciones}
    asignaciones = []
    vistos = set()
    for a in resultado.asignaciones:
        ob = por_numero.get(a.obligacion_numero)
        if not ob or ob["id"] in vistos:
            continue  # número inexistente o repetido: se descarta
        vistos.add(ob["id"])
        asignaciones.append({
            "obligacion_id": ob["id"],
            "obligacion_numero": ob["numero"],
            "obligacion_texto": ob["texto"],
            "confianza": round(a.confianza, 3),
            "nivel": nivel(a.confianza),
            "redaccion": a.redaccion,
            "justificacion": a.justificacion,
        })
        if len(asignaciones) == 3:
            break
    sin = resultado.sin_coincidencia or not asignaciones
    principal = asignaciones[0]["confianza"] if asignaciones else None
    return {
        "asignaciones": asignaciones,
        "sin_coincidencia": sin,
        "pregunta_aclaracion": resultado.pregunta_aclaracion,
        "nivel": nivel(principal, sin),
        "modelo": modelo,
    }
