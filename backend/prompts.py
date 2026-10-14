"""Prompts de la IA (sección 7 de la especificación)."""

# ------------------------------------------------------------------ 7.2 Minuta
SISTEMA_MINUTA = """Eres un asistente que lee minutas de contratos públicos colombianos y devuelve datos estructurados.
Responde SOLO con JSON válido. Si un dato no aparece, usa null. No inventes datos.
Clasifica tipo_contratacion como: prestacion_servicios, practica_formativa u otro.
El campo proyecto es el proyecto, programa o línea de trabajo al que se vincula el contrato, si se menciona.
Separa las obligaciones específicas de las generales. Conserva el texto de cada obligación completo y fiel."""

ESQUEMA_MINUTA = """{
  "contrato": {
    "numero": "string|null",
    "entidad": "string|null",
    "tipo_contratacion": "prestacion_servicios|practica_formativa|otro",
    "proyecto": "string|null",
    "objeto": "string|null",
    "dependencia": "string|null",
    "fecha_contrato": "YYYY-MM-DD|null",
    "fecha_inicio": "YYYY-MM-DD|null",
    "fecha_fin": "YYYY-MM-DD|null",
    "plazo_texto": "string|null",
    "valor_total": "number|null",
    "forma_pago": "string|null"
  },
  "contratista": { "nombre": "string|null", "cedula": "string|null" },
  "supervisor": { "nombre": "string|null", "cargo": "string|null" },
  "obligaciones": [
    { "numero": 1, "tipo": "especifica|general", "texto": "string", "palabras_clave": ["string"] }
  ]
}"""


def usuario_minuta(texto: str, especificas: list[str], generales: list[str]) -> str:
    partes = []
    if especificas:
        partes.append("Obligaciones ESPECÍFICAS ya separadas por numeración:\n"
                      + "\n".join(f"{i}. {t}" for i, t in enumerate(especificas, 1)))
    if generales:
        partes.append("Obligaciones GENERALES ya separadas por numeración:\n"
                      + "\n".join(f"{i}. {t}" for i, t in enumerate(generales, 1)))
    if partes:
        partes.append("IMPORTANTE: ya tenemos el texto exacto de estas obligaciones. En \"obligaciones\" devuelve una "
                      "entrada por cada una, con su numero, tipo y palabras_clave, y deja \"texto\" vacío (\"\"). "
                      "No copies el texto de las obligaciones.")
    detectadas = "\n\n".join(partes) if partes else ("(No se pudieron separar automáticamente; búscalas en el texto "
                                                     "y copia el texto completo y fiel de cada una.)")
    return f"""Extrae los datos de esta minuta.

Reglas adicionales:
- fecha_contrato es la fecha de suscripción o firma del contrato; fecha_inicio y fecha_fin son las de ejecución.
- Si las fechas de inicio y fin no aparecen, calcúlalas solo cuando el texto dé el plazo y una fecha de partida; si no, deja null.
- El supervisor suele aparecer en la cláusula de supervisión; si solo se menciona el cargo, deja nombre en null.
- palabras_clave: de 3 a 6 palabras que resuman cada obligación.

{detectadas}

Esquema de salida:
{ESQUEMA_MINUTA}

TEXTO DE LA MINUTA:
\"\"\"
{texto}
\"\"\""""


# ----------------------------------------------------------- 7.3 Clasificación
SISTEMA_CLASIFICAR = """Eres el asistente de un trabajador que redacta su informe mensual de actividades para su supervisor.
Te doy el tipo de contratación, el proyecto, el objeto del contrato y la lista numerada de obligaciones.
Tu trabajo:
1) Decide en cuál(es) obligación(es) encaja la actividad descrita. Puede encajar en más de una.
2) Mide la similitud con una confianza de 0 a 1. Si ninguna obligación encaja razonablemente, indica sin_coincidencia = true.
3) Redacta la actividad en español formal, en primera persona y pasado (por ejemplo: "Realicé el mantenimiento preventivo...").
4) NUNCA agregues hechos, cifras, nombres, lugares ni resultados que el trabajador no escribió.
   Si falta información útil, formula una sola pregunta breve en pregunta_aclaracion.
5) Ten en cuenta el tipo de contratación y el proyecto para interpretar la actividad en su contexto.
Responde SOLO con JSON válido.

Cómo debe quedar la redacción (es el texto que irá en el informe oficial):
- Lenguaje administrativo formal, claro y profesional; ortografía, tildes y puntuación correctas.
- Estructura: verbo en pretérito (realicé, efectué, brindé, elaboré, participé, apoyé…) + qué se hizo + sobre qué
  o dónde (solo si el trabajador lo dijo) + vínculo con la obligación usando sus propias palabras
  ("en desarrollo de…", "en el marco de…", "en cumplimiento de…").
- Una o dos oraciones completas, entre 20 y 55 palabras.
- Cambia expresiones coloquiales por términos técnicos equivalentes ("los computadores" -> "los equipos de cómputo",
  "arreglé" -> "solucioné" o "atendí", "el sistema se cayó" -> "la falla del sistema").
- Si el trabajador mencionó un resultado, agrégalo en una segunda oración que empiece por "Como resultado,".
- Prohibido inventar cantidades, nombres de personas, dependencias, herramientas, fechas o resultados. El vínculo con
  la obligación solo puede usar palabras que ya estén en la obligación.

Ejemplos de redacción (fíjate en que no se agrega ningún hecho nuevo):
Trabajador: "hoy hice mantenimiento a los computadores de la oficina" · Obligación: "REALIZAR SOPORTE TÉCNICO A LOS
EQUIPOS TECNOLÓGICOS... DEL DEPARTAMENTO ADMINISTRATIVO DE VALORIZACION DISTRITAL"
Redacción: "Realicé el mantenimiento de los equipos de cómputo de la oficina, en desarrollo del soporte técnico a los
equipos tecnológicos del Departamento Administrativo de Valorización Distrital."
Trabajador: "arregle la impresora que no imprimia y ya quedo funcionando" · Obligación: soporte técnico
Redacción: "Atendí la falla de la impresora, que no estaba imprimiendo, en el marco del soporte técnico a los equipos
tecnológicos de la dependencia. Como resultado, el equipo quedó nuevamente en funcionamiento."
Trabajador: "fui a la reunion del comite de sistemas" · Obligación: "ASISTIR A LAS REUNIONES A LAS QUE SE LE CONVOQUE"
Redacción: "Asistí a la reunión del comité de sistemas, en cumplimiento de la obligación de asistir a las reuniones a
las que se me convoque.\""""

ESQUEMA_CLASIFICAR = """{
  "asignaciones": [
    {
      "obligacion_numero": 1,
      "confianza": 0.0,
      "redaccion": "string",
      "justificacion": "una frase corta"
    }
  ],
  "sin_coincidencia": false,
  "pregunta_aclaracion": "string|null"
}"""


def usuario_clasificar(frase: str, fecha: str, contrato: dict, obligaciones: list[dict]) -> str:
    lista = "\n".join(f"{o['numero']}. {o['texto']}" for o in obligaciones)
    return f"""Tipo de contratación: {contrato.get('tipo_contratacion') or 'prestacion_servicios'}
Proyecto: {contrato.get('proyecto') or 'No especificado'}
Objeto del contrato: {contrato.get('objeto') or 'No especificado'}
Fecha de la actividad: {fecha}

Obligaciones específicas:
{lista}

Actividad descrita por el trabajador:
\"\"\"{frase}\"\"\"

Indicaciones:
- Devuelve hasta 3 asignaciones, ordenadas de mayor a menor confianza.
- Usa una obligación genérica (por ejemplo "las demás que le sean asignadas") solo si ninguna otra encaja.
- En la redacción no uses palabras relativas de tiempo como "hoy" o "ayer"; la fecha ya queda registrada.

Esquema de salida:
{ESQUEMA_CLASIFICAR}"""


# ------------------------------------------------------- Anexos (evidencias)
SISTEMA_EVIDENCIA = """Redactas la descripción de un anexo (evidencia) para un informe oficial de actividades de una entidad
pública colombiana. La descripción identifica el soporte y debe corresponder a la actividad y a la obligación.
Reglas:
- Una sola frase nominal, en español formal, de 8 a 25 palabras, sin punto final.
- Empieza según el tipo de archivo: imagen -> "Registro fotográfico de…"; documento -> "Documento soporte de…";
  hoja de cálculo -> "Archivo de soporte de…".
- Describe la actividad realizada (no el archivo). No menciones el nombre del archivo ni su extensión.
- NUNCA agregues hechos, cantidades, nombres, lugares o resultados que no estén en la actividad.
Responde SOLO con JSON válido: {"descripcion": "string"}"""


def usuario_evidencia(actividad: str, obligacion: str, tipo: str) -> str:
    return f"""Tipo de archivo: {tipo}
Actividad (tal como quedó en el informe): {actividad}
Obligación a la que corresponde: {obligacion or 'Sin obligación asignada'}

Ejemplo: actividad "Realicé el mantenimiento de los equipos de cómputo de la oficina, en desarrollo del soporte técnico..."
tipo imagen -> {{"descripcion": "Registro fotográfico del mantenimiento realizado a los equipos de cómputo de la oficina"}}"""


# ------------------------------------------------------- 8.2 Mapa de plantilla
SISTEMA_MAPA = """Analizas la estructura de una plantilla Word de informe de actividades de una entidad pública colombiana.
Te doy sus tablas (con índices de tabla, fila y columna) y sus párrafos (con índice).
Indica dónde se escribe cada dato. Usa solo índices que aparezcan en la estructura. Si no encuentras un dato, usa null.
Responde SOLO con JSON válido."""

ESQUEMA_MAPA = """{
  "campos": {
    "nombre_contratista": {"tabla": 0, "fila": 1, "col": 1} ,
    "numero_contrato": {"tabla": 0, "fila": 2, "col": 1},
    "fecha_contrato": null,
    "objeto": null,
    "cedula": null,
    "fecha_inicio": null,
    "fecha_fin": null,
    "dependencia": null,
    "supervisor": null
  },
  "ejecucion": {"tabla": 1, "fila_encabezado": 1, "col_item": 0, "col_obligacion": 1, "col_actividades": 2},
  "parrafo_fecha_elaboracion": null,
  "parrafo_tipo_informe": null,
  "parrafo_periodo": null
}"""


def usuario_mapa(estructura: str, faltantes: list[str]) -> str:
    return f"""Faltan por ubicar: {', '.join(faltantes)}.
La celda de un dato es la que queda a la derecha de su etiqueta (col de la etiqueta + 1).
La tabla de ejecución es la que tiene columnas de obligaciones y de actividades.

ESTRUCTURA:
{estructura}

Esquema de salida (ejemplo de formato, no de valores):
{ESQUEMA_MAPA}"""
