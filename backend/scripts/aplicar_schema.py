"""Ejecuta supabase/schema.sql en la base de datos de Supabase.

Uso (PowerShell), con la contraseña de la base de datos del proyecto:
    $env:PGPASSWORD = "tu-contraseña"
    python scripts/aplicar_schema.py

Por defecto se conecta por el pooler de Supabase (IPv4), porque la conexión
directa db.<ref>.supabase.co solo funciona en redes con IPv6. Se puede cambiar
con las variables PGHOST, PGPORT y PGUSER.
"""
import os
import sys
from pathlib import Path

import psycopg

RAIZ = Path(__file__).resolve().parents[2]
SCHEMA = RAIZ / "supabase" / "schema.sql"
REF = os.environ.get("SUPABASE_REF", "yzzfplbhnyexczxnselo")


def main():
    if not os.environ.get("PGPASSWORD"):
        sys.exit("Falta PGPASSWORD (contraseña de la base de datos de Supabase).")
    sql = SCHEMA.read_text(encoding="utf-8")
    params = dict(
        host=os.environ.get("PGHOST", "aws-1-us-west-2.pooler.supabase.com"),
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ.get("PGUSER", f"postgres.{REF}"),
        dbname=os.environ.get("PGDATABASE", "postgres"),
        sslmode="require",
        connect_timeout=20,
    )
    with psycopg.connect(**params) as conn:
        conn.execute(sql)
        conn.commit()
        tablas = conn.execute(
            "select string_agg(table_name, ', ' order by table_name) from information_schema.tables "
            "where table_schema = 'public'").fetchone()[0]
        buckets = conn.execute("select string_agg(id, ', ' order by id) from storage.buckets").fetchone()[0]
        planes = conn.execute("select string_agg(id || '=' || precio_cop, ', ' order by precio_cop) from public.planes").fetchone()[0]
    print("Esquema aplicado.")
    print("Tablas:", tablas)
    print("Buckets:", buckets)
    print("Planes:", planes)


if __name__ == "__main__":
    main()
