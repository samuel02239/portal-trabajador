"""Cédula del contratista: debe aparecer en la minuta y se muestra oculta en los mensajes."""
from servicios.cedulas import aparece_en_texto, normalizar, ocultar_cedula, ocultar_correo

TEXTO = ("y por la otra, PERSONA DE PRUEBA EJEMPLO, identificado(a) con la Cédula de Ciudadanía No. 1012345678, "
         "actuando en su propio nombre ... NIT 890480184-4 ... teléfono 3001234567")


def test_aparece_en_texto():
    assert aparece_en_texto("1012345678", TEXTO)
    assert aparece_en_texto("1.012.345.678", TEXTO)
    assert aparece_en_texto("1012345678", "C.C. 1.012.345.678 de Cartagena")
    assert aparece_en_texto("1012345678", "conlaCéduladeCiudadaníaNo.1012345678,actuando")  # PDF sin espacios
    assert not aparece_en_texto("345678", "C.C. 1.012.345.678")  # pedazo de una cédula con puntos
    assert not aparece_en_texto("1012345", "C.C. 1.012.345.678")
    assert not aparece_en_texto("2345678", TEXTO)        # parte de un número más largo
    assert not aparece_en_texto("890480184", TEXTO)      # es el NIT de la entidad (890480184-4), no una cédula
    assert not aparece_en_texto("300123456", TEXTO)      # parte de un teléfono
    assert not aparece_en_texto("12345678", TEXTO)
    assert not aparece_en_texto("123", TEXTO)           # demasiado corta


def test_normalizar_y_ocultar():
    assert normalizar(" 1.012.345-678 ") == "1012345678"
    assert ocultar_correo("persona.prueba@gmail.com") == "pe***@gmail.com"
    assert ocultar_correo(None) == "otra cuenta"
    assert ocultar_cedula("1012345678") == "****5678"
