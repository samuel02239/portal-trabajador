"""El instalador que se reparte solo se crea con servidor remoto https y llave pública."""
import importlib.util
from pathlib import Path

_ruta = Path(__file__).resolve().parents[1] / "scripts" / "revisar_distribucion.py"
_spec = importlib.util.spec_from_file_location("revisar_distribucion", _ruta)
revisar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(revisar)

LISTO = {"MODO_BACKEND": "remoto", "API_BASE_URL": "https://portal-trabajador-api.onrender.com",
         "SUPABASE_URL": "https://x.supabase.co", "SUPABASE_ANON_KEY": "sb_publishable_abc"}


def test_configuracion_lista():
    assert revisar.problemas(LISTO) == []


def test_rechaza_modo_integrado_y_servidor_local():
    lista = revisar.problemas({**LISTO, "MODO_BACKEND": "integrado", "API_BASE_URL": "http://127.0.0.1:8000"})
    assert len(lista) == 2


def test_rechaza_llaves_secretas():
    lista = revisar.problemas({**LISTO, "SUPABASE_ANON_KEY": "sb_secret_xyz", "OPENROUTER_API_KEYS": "sk-or-v1-x"})
    assert any("pública" in p for p in lista) and any("OPENROUTER_API_KEYS" in p for p in lista)
