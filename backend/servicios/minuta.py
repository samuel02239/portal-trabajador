"""Lectura de la minuta (sección 7.2).

1. Se localizan las cláusulas de obligaciones específicas y generales.
2. Se separan por numeración con expresiones regulares ANTES de llamar a la IA
   (en las minutas suelen venir en un solo párrafo: "1. ...; 2. ...").
3. La IA devuelve el JSON del contrato. Para las obligaciones se conserva el
   texto exacto del documento cuando la numeración se pudo separar.
4. Si la IA no está disponible, se devuelve lo que se pudo extraer con reglas
   para que el trabajador complete el resto en la pantalla de revisión.
"""
from __future__ import annotations

import logging
import re

import prompts
from ia import IAError, IANoConfigurada, llamar_ia
from schemas import MinutaIA, a_numero, a_texto

log = logging.getLogger("portal.minuta")

MAX_TEXTO_IA = 60000

_FIN_CLAUSULA = r"(?:PAR[AÁ]GRAFO|CL[AÁ]USULA\s+\d+|CLA[UÚ]SULA\s+\d+|OBLIGACIONES\s+GENERALES|$)"


def limpiar(texto: str) -> str:
    """Une las líneas en un solo texto con espacios simples."""
    return re.sub(r"\s+", " ", texto or "").strip()


def _segmento(texto: str, inicio_patron: str) -> str:
    m = re.search(inicio_patron, texto, flags=re.I)
    if not m:
        return ""
    resto = texto[m.end():]
    fin = re.search(_FIN_CLAUSULA, resto, flags=re.I)
    return resto[:fin.start()] if fin else resto


def localizar_clausulas(texto: str) -> tuple[str, str]:
    """Devuelve (texto de obligaciones específicas, texto de obligaciones generales)."""
    t = limpiar(texto)
    especificas = _segmento(t, r"OBLIGACIONES\s+ESPEC[IÍ]FICAS[^:]{0,80}:")
    generales = _segmento(t, r"OBLIGACIONES\s+GENERALES(?!\s+DEL\s+CONTRATANTE)[^:]{0,80}:")
    return especificas, generales


_NUMERO = re.compile(r"(?:^|(?<=[\s;:.]))(\d{1,2})\s?[.)]\s+")


def dividir_numeradas(segmento: str) -> list[str]:
    """Separa '1. xxx; 2. yyy; ...' respetando la secuencia 1, 2, 3...

    Un número fuera de secuencia (p. ej. un '6.' repetido) se queda dentro del
    texto de la obligación anterior en vez de partirla.
    """
    if not segmento:
        return []
    aceptados = []
    esperado = 1
    for m in _NUMERO.finditer(segmento):
        if int(m.group(1)) == esperado:
            aceptados.append(m)
            esperado += 1
    if len(aceptados) < 2:
        return []
    items = []
    for i, m in enumerate(aceptados):
        fin = aceptados[i + 1].start() if i + 1 < len(aceptados) else len(segmento)
        texto = segmento[m.end():fin].strip()
        texto = re.sub(r"\s*[;,]\s*$", "", texto)          # separador final
        texto = re.sub(r"\.{2,}$", ".", texto).strip()        # 'CONTRACTUAL..' -> 'CONTRACTUAL.'
        if texto:
            items.append(texto)
    return items


def _buscar(patron: str, texto: str, grupo: int = 1) -> str | None:
    m = re.search(patron, texto, flags=re.I | re.S)
    return a_texto(m.group(grupo)) if m else None


def extraer_basico(texto: str) -> dict:
    """Datos que se pueden sacar con reglas, como respaldo de la IA."""
    t = limpiar(texto)
    nombre, cedula = None, None
    m = re.search(r"por la otra,\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ]{4,80}?)\s*,\s*identificad[oa](?:\(a\))?\s+con\s+la\s+"
                  r"c[eé]dula\s+de\s+ciudadan[ií]a\s+(?:No\.?|N[°º])\s*([\d.]+)", t, flags=re.I)
    if m:
        nombre, cedula = a_texto(m.group(1)), m.group(2).replace(".", "")
    numero = _buscar(r"(?:ANEXO\s+T[EÉ]CNICO|CONTRATO)\s+(?:No\.?|N[°º]\.?|N[UÚ]MERO)\s*([\w\-]+)", t)
    objeto = _buscar(r"OBJETO\s+DEL\s+CONTRATO\s*:\s*(.+?)(?=\s+CL[AÁ]USULA\s+\d)", t)
    entidad = _buscar(r"en\s+nombre\s+y\s+representaci[oó]n\s+del?\s+(.+?),\s*con\s+NIT", t)
    plazo = _buscar(r"PLAZO\s+DE\s+EJECUCI[OÓ]N\s*:\s*(.+?\.)\s", t)
    valor_txt = _buscar(r"VALOR\s+DEL\s+CONTRATO.{0,250}?\(\s*\$\s*([\d.,]+)\s*\)", t)
    forma_pago = _buscar(r"(pagar[aá]\s+al\s+Contratista\s+el\s+valor\s+del\s+contrato\s+.+?)(?=\s+Los\s+anteriores|\.\s)", t)
    cargo_sup = _buscar(r"SUPERVISI[OÓ]N\s*:.{0,250}?estar[aá]\s+a\s+cargo\s+del?\s+(.+?)\.(?:\s|$)", t)
    dependencia = _buscar(r"funciones\s+propias\s+de\s+(?:la|el)\s+(.+?)\.", t)
    tipo = "practica_formativa" if re.search(r"pr[aá]ctica\s+(?:formativa|laboral)", t, re.I) else "prestacion_servicios"
    return {
        "contrato": {
            "numero": numero, "entidad": entidad, "tipo_contratacion": tipo, "proyecto": None,
            "objeto": objeto, "dependencia": dependencia, "fecha_contrato": None, "fecha_inicio": None,
            "fecha_fin": None, "plazo_texto": plazo, "valor_total": a_numero(valor_txt),
            "forma_pago": forma_pago,
        },
        "contratista": {"nombre": nombre, "cedula": cedula},
        "supervisor": {"nombre": None, "cargo": cargo_sup},
    }


def _fusionar(principal: dict, respaldo: dict) -> dict:
    """Completa los vacíos de 'principal' con 'respaldo' (sin pisar lo que ya tiene)."""
    salida = dict(principal)
    for k, v in respaldo.items():
        if isinstance(v, dict):
            salida[k] = _fusionar(principal.get(k) or {}, v)
        elif salida.get(k) in (None, "", []):
            salida[k] = v
    return salida


def analizar_minuta(texto: str, user_id: str | None = None) -> dict:
    """Devuelve {'datos': {...}, 'avisos': [...], 'modelo': str|None} para la pantalla de revisión."""
    avisos: list[str] = []
    esp_txt, gen_txt = localizar_clausulas(texto)
    especificas = dividir_numeradas(esp_txt)
    generales = dividir_numeradas(gen_txt)
    basico = extraer_basico(texto)

    datos_ia: dict | None = None
    modelo = None
    try:
        mensajes = [
            {"role": "system", "content": prompts.SISTEMA_MINUTA},
            {"role": "user", "content": prompts.usuario_minuta(texto[:MAX_TEXTO_IA], especificas, generales)},
        ]
        # Si la numeración ya separó las obligaciones, la IA no repite su texto: responde mucho más rápido
        objeto, modelo = llamar_ia("extraer_minuta", mensajes, MinutaIA, user_id=user_id,
                                   max_tokens=2000 if especificas else 6000)
        datos_ia = objeto.model_dump(mode="json")
    except IANoConfigurada as exc:
        avisos.append(f"La IA no está disponible: {exc} Extraje lo que pude con reglas; revisa y completa.")
    except IAError:
        avisos.append("No pudimos analizar la minuta con IA en este momento. Extraje lo que pude; "
                      "revisa y completa los datos.")

    if datos_ia is None:
        datos_ia = {**basico, "obligaciones": []}
    else:
        datos_ia = _fusionar(datos_ia, basico)

    obligaciones_ia = datos_ia.get("obligaciones") or []
    claves = {(o["tipo"], o["numero"]): o.get("palabras_clave") or [] for o in obligaciones_ia}
    finales: list[dict] = []
    for tipo, lista in (("especifica", especificas), ("general", generales)):
        de_ia = sorted((o for o in obligaciones_ia if o["tipo"] == tipo), key=lambda o: o["numero"])
        if lista:
            if de_ia and len(de_ia) != len(lista):
                avisos.append(f"La IA encontró {len(de_ia)} obligaciones {tipo}s y la numeración del documento tiene "
                              f"{len(lista)}; se usó la numeración del documento.")
            finales += [{"numero": i, "tipo": tipo, "texto": t, "palabras_clave": claves.get((tipo, i), [])}
                        for i, t in enumerate(lista, 1)]
        else:
            finales += [{"numero": o["numero"], "tipo": tipo, "texto": o["texto"],
                         "palabras_clave": o.get("palabras_clave") or []} for o in de_ia if len(o["texto"]) >= 3]
    datos_ia["obligaciones"] = finales

    if not any(o["tipo"] == "especifica" for o in finales):
        avisos.append("No encontramos las obligaciones específicas. Agrégalas a mano en la revisión.")
    c = datos_ia["contrato"]
    if not c.get("fecha_inicio") or not c.get("fecha_fin"):
        avisos.append("La minuta no trae las fechas de inicio y terminación; escríbelas en la revisión.")
    if not (datos_ia.get("supervisor") or {}).get("nombre"):
        avisos.append("Escribe el nombre del supervisor: la minuta solo trae su cargo o no lo menciona.")
    return {"datos": datos_ia, "avisos": avisos, "modelo": modelo}
