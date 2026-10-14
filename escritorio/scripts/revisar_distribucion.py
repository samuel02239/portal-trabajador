"""Revisa escritorio/.env antes de crear el instalador que se reparte a los trabajadores.

El instalador debe usar el servidor en la nube (MODO_BACKEND=remoto + https) y llevar solo la llave pública
de Supabase. Si algo no cumple, construir.bat se detiene.

Uso:  python scripts/revisar_distribucion.py      (lo llama construir.bat)
"""
import sys
from pathlib import Path

from dotenv import dotenv_values

ENV = Path(__file__).resolve().parents[1] / ".env"


def problemas(valores: dict) -> list[str]:
    salida = []
    modo = (valores.get("MODO_BACKEND") or "remoto").strip().lower()
    api = (valores.get("API_BASE_URL") or "").strip()
    llave = (valores.get("SUPABASE_ANON_KEY") or "").strip()
    if modo != "remoto":
        salida.append("MODO_BACKEND debe ser 'remoto' (el modo integrado necesita las llaves secretas en cada PC).")
    if not api.startswith("https://") or "127.0.0.1" in api or "localhost" in api:
        salida.append("API_BASE_URL debe ser la dirección https:// del servidor en la nube.")
    if not (valores.get("SUPABASE_URL") or "").startswith("https://"):
        salida.append("SUPABASE_URL debe empezar por https://.")
    if not llave.startswith("sb_publishable_"):
        salida.append("SUPABASE_ANON_KEY debe ser la llave pública (sb_publishable_...). Nunca la secreta.")
    secretas = [k for k in valores if k.startswith(("OPENROUTER", "WOMPI")) or k == "SUPABASE_SERVICE_ROLE_KEY"]
    if secretas:
        salida.append(f"Quita de escritorio/.env estas variables secretas: {', '.join(secretas)}.")
    return salida


def main() -> int:
    if not ENV.exists():
        print(f"No existe {ENV}")
        return 1
    lista = problemas(dotenv_values(ENV))
    if lista:
        print("El instalador NO se puede crear todavía. Corrige escritorio/.env:")
        for p in lista:
            print(f"  - {p}")
        return 1
    print("escritorio/.env listo para repartir (servidor remoto con https, solo llave pública).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
