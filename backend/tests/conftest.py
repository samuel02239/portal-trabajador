import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

PLANTILLA = BASE / "plantillas_base" / "GDOGC01-F007.docx"


@pytest.fixture
def plantilla_bytes() -> bytes:
    return PLANTILLA.read_bytes()


# Minuta sintética con la misma estructura de las minutas reales (un solo párrafo con "1. ...; 2. ...")
MINUTA_TEXTO = (
    "ANEXO TÉCNICO No. 1234 DEL CONTRATO ELECTRONICO SECOP II. Entre los suscritos: FUNCIONARIA DE PRUEBA, "
    "actuando en nombre y representación del Distrito Turístico y Cultural de Cartagena de Indias, con NIT 890480184-4, "
    "por una parte; y por la otra, PERSONA DE PRUEBA EJEMPLO, identificado(a) con la Cédula de Ciudadanía No. 1000000001, "
    "actuando en su propio nombre. I. Que existe insuficiencia de personal de planta para cumplir las funciones propias "
    "de la OFICINA DE PRUEBA. CLÁUSULA 1 - OBJETO DEL CONTRATO: PRESTACIÓN DE SERVICIOS DE APOYO A LA GESTIÓN EN LA "
    "OFICINA DE PRUEBA. CLÁUSULA 2 - OBLIGACIONES ESPECÍFICAS DEL CONTRATO: 1. REALIZAR SOPORTE TÉCNICO A LOS EQUIPOS "
    "TECNOLÓGICOS DE LA DEPENDENCIA; 2. REALIZAR SEGUIMIENTO A LOS INCIDENTES CONFORME A LA LEY 1150 DE 2007; "
    "3. ASISTIR A LAS REUNIONES A LAS QUE SE LE CONVOQUE; 4. LAS DEMAS QUE LE SEAN ASIGNADAS.. PARÁGRAFO PRIMERO: "
    "Serán de propiedad de la Entidad los resultados. CLÁUSULA 4 - VALOR DEL CONTRATO Y FORMA DE PAGO: El valor del "
    "presente Contrato corresponde a la suma de: TRES MILLONES DE PESOS MCTE ($3,000,000.00). CLÁUSULA 6 - PLAZO DE "
    "EJECUCIÓN: El plazo de ejecución del presente Contrato será de DOS (2) meses. PARÁGRAFO: nada. "
    "CLÁUSULA 8 - OBLIGACIONES GENERALES DEL CONTRATISTA: El Contratista se obliga a: 1. Cumplir con lo pactado. "
    "2. Asistir a las reuniones. 3. Estar afiliado al sistema según el artículo 50 de la ley 789 de 2002. "
    "3. Cumplir con el sistema de riesgos laborales. 4. Responder por los insumos. PARÁGRAFO: En los casos... "
    "CLÁUSULA 10 - OBLIGACIONES GENERALES DEL CONTRATANTE: 1. Ejercer el control. 2. Pagar. "
    "CLÁUSULA 22 - SUPERVISIÓN: La supervisión de la ejecución estará a cargo del JEFE DE LA OFICINA DE PRUEBA. "
    "CLÁUSULA 23 - ANEXOS."
)
