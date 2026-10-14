import os
import sys
from pathlib import Path

import pytest

os.environ["PORTAL_KEYRING_SERVICIO"] = "PortalTrabajadorPruebas"  # las pruebas no tocan la sesión real
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def obligaciones():
    return [{"id": f"o{i}", "numero": i, "tipo": "especifica", "texto": f"OBLIGACIÓN {i} DE PRUEBA",
             "titulo_corto": f"Obligación {i} de prueba"} for i in range(1, 6)]


class GestorFalso:
    """Imita GestorSesion sin keyring ni red."""

    def __init__(self, tokens=("t1", "t2")):
        self.tokens = list(tokens)
        self.sesion = object()
        self.renovaciones = 0

    def token(self, forzar=False):
        if forzar:
            self.renovaciones += 1
            self.tokens.pop(0)
        return self.tokens[0]


@pytest.fixture
def gestor():
    return GestorFalso()
