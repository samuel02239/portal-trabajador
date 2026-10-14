"""Prueba de punta a punta contra Supabase real y el backend encendido.

Crea usuarios de prueba, recorre el flujo completo y verifica:
- Fase 0: el usuario nuevo queda con el plan gratis.
- Fase 2: la minuta de ejemplo produce las 10 obligaciones específicas.
- Cédula: una cédula = una cuenta; la cédula debe aparecer en la minuta; no se puede cambiar.
- Fase 5: 1 informe gratis; el segundo recibe 402; regenerar no cobra; borrar la cuenta y crear otra no da más informes gratis (la prueba es por cédula).
- Fase 7: ningún usuario ve datos del otro (RLS y API).
Al final borra todo lo creado.

Uso:  python scripts/prueba_integral.py ruta/minuta.pdf   (con el backend en API_PRUEBA o http://127.0.0.1:8000)
"""
import concurrent.futures as cf
import hashlib
import io
import os
import random
import re
import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from config import cfg  # noqa: E402
from db import get_db  # noqa: E402

API = os.environ.get("API_PRUEBA", "http://127.0.0.1:8000") + "/api"
PUB = {"apikey": cfg.supabase_anon_key}
CLAVE = "Clave-Prueba-123"
resultados = []


def ok(cond, texto):
    resultados.append(bool(cond))
    print(("  OK   " if cond else "  FALLA ") + texto)
    return cond


def login(email):
    r = httpx.post(f"{cfg.supabase_url}/auth/v1/token?grant_type=password", headers=PUB,
                   json={"email": email, "password": CLAVE}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def cliente(token):
    return httpx.Client(base_url=API, headers={"Authorization": f"Bearer {token}"}, timeout=240)


def minuta_sintetica(cedula: str) -> bytes:
    """Minuta en Word con la misma estructura de las reales y la cédula indicada."""
    from docx import Document
    sys.path.insert(0, str(BASE / "tests"))
    from conftest import MINUTA_TEXTO
    doc = Document()
    doc.add_paragraph(MINUTA_TEXTO.replace("1000000001", f"{int(cedula):,}".replace(",", ".")))  # 1.0xx.xxx.xxx
    salida = io.BytesIO()
    doc.save(salida)
    return salida.getvalue()


def leer(c, contenido: bytes, nombre: str, tipo: str):
    return c.post("/contratos/minuta", files={"archivo": (nombre, contenido, tipo)})


def guardar(c, lectura: dict, cedula: str | None = None, hoy=None):
    hoy = hoy or date.today()
    d = lectura["datos"]
    contrato = {"numero_contrato": d["contrato"].get("numero") or "PRUEBA", "objeto": d["contrato"].get("objeto"),
                "dependencia": d["contrato"].get("dependencia"), "supervisor_nombre": "SUPERVISOR DE PRUEBA",
                "fecha_inicio": (hoy.replace(day=1) - timedelta(days=62)).replace(day=1).isoformat(),
                "fecha_fin": (hoy.replace(day=28) + timedelta(days=40)).isoformat()}
    contratista = {"nombre": d["contratista"].get("nombre") or "PERSONA DE PRUEBA",
                   "cedula": cedula if cedula is not None else d["contratista"].get("cedula")}
    return c.post("/contratos", json={"lectura_id": lectura["lectura_id"], "contrato": contrato,
                                      "contratista": contratista, "obligaciones": d["obligaciones"]})


def main():
    minuta_real = Path(sys.argv[1]).read_bytes()
    db = get_db()
    sufijo = secrets.token_hex(3)
    usuarios = []

    def nuevo(letra):
        email = f"prueba.{letra}.{sufijo}@example.com"
        u = db.crear_usuario(email, CLAVE, f"Usuario {letra.upper()} Prueba")
        usuarios.append((u["id"], email))
        return u["id"], email, cliente(login(email))

    cedula_a = str(random.randint(1_000_000_000, 1_099_999_999))
    docx_a = minuta_sintetica(cedula_a)
    tipo_docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    try:
        ida, ema, A = nuevo("a")
        idb, emb, B = nuevo("b")

        print("Fase 0 · usuario nuevo")
        s = A.get("/suscripcion/actual").json()
        ok(s["plan"] == "gratis" and s["restantes"] == 1, f"plan gratis con 1 informe (restantes={s['restantes']})")

        print("Fase 2 · minuta de ejemplo (real)")
        r = leer(A, minuta_real, "minuta.pdf", "application/pdf")
        ok(r.status_code == 200, f"lectura de minuta HTTP {r.status_code}")
        real = r.json()
        esp = [o for o in real["datos"]["obligaciones"] if o["tipo"] == "especifica"]
        ok(len(esp) == 10, f"10 obligaciones específicas (salieron {len(esp)})")
        ok("texto_extraido" not in real and real.get("lectura_id"), "el texto de la minuta se queda en el servidor")
        cedula_real = re.sub(r"\D", "", real["datos"]["contratista"].get("cedula") or "")
        dueno = db.uno("profiles", {"cedula": cedula_real}, "id") if cedula_real else None
        if dueno:
            ok(any("ya está vinculada a otra cuenta" in a for a in real["avisos"]),
               "avisa al leer una minuta cuya cédula ya tiene cuenta")
            r = guardar(A, real)
            ok(r.status_code == 409 and r.json()["error"]["codigo"] == "cedula_en_uso",
               f"no deja guardar un contrato con la cédula de otra cuenta (HTTP {r.status_code})")
        r = guardar(A, real, cedula="12345678")
        ok(r.status_code == 400 and r.json()["error"]["codigo"] == "cedula_no_en_minuta",
           f"rechaza una cédula que no aparece en la minuta (HTTP {r.status_code})")

        print("Cédula · una cédula = una cuenta")
        lectura_a = leer(A, docx_a, "minuta_a.docx", tipo_docx).json()
        r = guardar(A, lectura_a)
        ok(r.status_code == 200, f"A guarda su contrato (HTTP {r.status_code} {r.text[:150] if r.status_code != 200 else ''})")
        obligs = r.json().get("obligaciones", [])
        perfil_a = db.uno("profiles", {"id": ida}, "cedula")
        ok(perfil_a["cedula"] == cedula_a, "la cédula queda vinculada a la cuenta A")
        lectura_b = leer(B, docx_a, "misma_minuta.docx", tipo_docx).json()
        ok(any("ya está vinculada" in a for a in lectura_b["avisos"]), "B ve el aviso al leer la minuta de A")
        r = guardar(B, lectura_b)
        ok(r.status_code == 409 and r.json()["error"]["codigo"] == "cedula_en_uso",
           f"B no puede registrar la misma minuta/cédula en otra cuenta (HTTP {r.status_code})")
        contrato_a = A.get("/contratos/actual").json()["contrato"]
        r = A.put(f"/contratos/{contrato_a['id']}", json={"contrato": {"numero_contrato": "X"},
                                                          "contratista": {"nombre": "A", "cedula": "999999999"},
                                                          "obligaciones": [{"id": o["id"], "numero": o["numero"],
                                                                            "tipo": o["tipo"], "texto": o["texto"]}
                                                                           for o in obligs]})
        ok(r.status_code == 409, f"A no puede cambiar la cédula de su contrato (HTTP {r.status_code})")
        r = httpx.patch(f"{cfg.supabase_url}/rest/v1/profiles", params={"id": f"eq.{ida}"},
                        headers={**PUB, "Authorization": A.headers["Authorization"]}, json={"cedula": "111111111"})
        ok(r.status_code >= 400, f"A no puede cambiar su cédula directo en la base de datos (HTTP {r.status_code})")
        cab_a = {**PUB, "Authorization": A.headers["Authorization"]}
        r = httpx.post(f"{cfg.supabase_url}/rest/v1/contratos", headers=cab_a,
                       json={"user_id": ida, "numero_contrato": "DIRECTO", "cedula_contratista": "123456789"})
        ok(r.status_code >= 400, f"A no puede crear contratos saltándose el backend (HTTP {r.status_code})")
        r = httpx.patch(f"{cfg.supabase_url}/rest/v1/obligaciones", headers={**cab_a, "Prefer": "return=representation"},
                        params={"id": f"eq.{obligs[0]['id']}"}, json={"texto": "CAMBIADA DIRECTO"})
        ok(r.status_code >= 400, f"A no puede cambiar obligaciones saltándose el backend (HTTP {r.status_code})")
        r = httpx.post(f"{cfg.supabase_url}/storage/v1/object/evidencias/{ida}/basura.png",
                       headers={**cab_a, "Content-Type": "image/png"}, content=b"\x89PNG\r\n\x1a\n" + b"0" * 1000)
        ok(r.status_code >= 400, f"A no puede subir archivos directo al almacenamiento (HTTP {r.status_code})")

        print("Fase 3/4 · actividades e informe")
        o1 = next(o for o in obligs if o["tipo"] == "especifica" and o["numero"] == 1)
        hoy = date.today()
        meses = [hoy.replace(day=5), (hoy.replace(day=1) - timedelta(days=1)).replace(day=5),
                 (hoy.replace(day=1) - timedelta(days=32)).replace(day=5)]
        informes = []
        for m in meses:
            r = A.post("/actividades", json={"fecha": m.isoformat(), "texto_original": "hice mantenimiento",
                                             "texto_redactado": "Realicé el mantenimiento de los equipos de cómputo.",
                                             "obligacion_id": o1["id"], "confianza": 0.92, "estado": "confirmada"})
            ok(r.status_code == 200, f"actividad del {m} guardada")
            informes.append(A.get("/informes/actual", params={"periodo": m.strftime("%Y-%m")}).json()["informe"]["id"])

        print("Fase 5 · generación y cupo")
        r = A.post(f"/informes/{informes[0]}/generar", json={"tipo": "parcial"})
        ok(r.status_code == 200 and r.json()["cobrado"], f"1er informe generado y cobrado (HTTP {r.status_code})")
        r = A.post(f"/informes/{informes[0]}/generar", json={"tipo": "final"})
        ok(r.status_code == 200 and not r.json()["cobrado"], "regenerar el mismo informe no cobra")
        with cf.ThreadPoolExecutor(2) as ex:
            rs = [f.result() for f in [ex.submit(A.post, f"/informes/{informes[1]}/generar", json={"tipo": "parcial"})
                                       for _ in range(2)]]
        ok(all(x.status_code == 402 for x in rs), f"agotado el cupo gratis, otro informe recibe 402 ({[x.status_code for x in rs]})")
        r = A.get(f"/informes/{informes[0]}/descargar", params={"formato": "pdf"})
        ok(r.status_code == 200 and httpx.get(r.json()["url"], timeout=60).content.startswith(b"%PDF"),
           "descarga del PDF con URL firmada")

        print("Fase 7 · aislamiento entre usuarios")
        cab_b = {**PUB, "Authorization": B.headers["Authorization"]}
        for tabla in ("contratos", "obligaciones", "informes", "actividades", "evidencias", "pagos",
                      "consumo_informes", "suscripciones", "profiles", "lecturas_minuta", "pruebas_gratis"):
            r = httpx.get(f"{cfg.supabase_url}/rest/v1/{tabla}", headers=cab_b, params={"select": "*"})
            filas = r.json() if r.status_code == 200 else []
            ajenas = [f for f in filas if (f.get("user_id") or f.get("id")) == ida] if isinstance(filas, list) else []
            if tabla in ("obligaciones", "pruebas_gratis"):  # B no tiene contrato; la prueba gratis no es de nadie
                ajenas = filas if isinstance(filas, list) else []
            ok(not ajenas, f"B no ve {tabla} de A")
        r = B.get(f"/informes/{informes[0]}/descargar", params={"formato": "pdf"})
        ok(r.status_code == 404, f"B no puede descargar el informe de A (HTTP {r.status_code})")
        r = httpx.patch(f"{cfg.supabase_url}/rest/v1/profiles", headers={**cab_b, "Prefer": "return=representation"},
                        params={"id": f"eq.{idb}"}, json={"rol": "admin"})
        ok(r.status_code >= 400, f"B no puede volverse admin (HTTP {r.status_code})")

        print("Prueba gratis por cédula · borrar la cuenta no da más informes")
        r = A.delete("/cuenta")
        ok(r.status_code == 200, "A elimina su cuenta")
        usuarios[:] = [x for x in usuarios if x[0] != ida]
        ida2, ema2, A2 = nuevo("a2")
        lectura = leer(A2, docx_a, "minuta_a.docx", tipo_docx).json()
        r = guardar(A2, lectura)
        ok(r.status_code == 200, f"con la cuenta borrada, la cédula queda libre para una cuenta nueva (HTTP {r.status_code})")
        s = A2.get("/suscripcion/actual").json()
        ok(s["restantes"] == 0, f"la cuenta nueva NO recibe otro informe gratis (restantes={s['restantes']})")
    finally:
        print("Limpieza")
        for uid, email in usuarios:
            try:
                r = cliente(login(email)).delete("/cuenta")
                print(f"  cuenta {email} eliminada: HTTP {r.status_code}")
            except Exception as exc:
                db.borrar_usuario(uid)
                print(f"  {email} borrado por admin ({type(exc).__name__})")
        db.borrar("pruebas_gratis", {"cedula_hash": hashlib.sha256(cedula_a.encode()).hexdigest()})
    print(f"\n{sum(resultados)}/{len(resultados)} verificaciones OK")
    sys.exit(0 if all(resultados) else 1)


if __name__ == "__main__":
    main()
