"""Verifica las cuentas de prueba sin límite contra Supabase real (con el backend encendido).

Crea un usuario temporal, lo agrega a cuentas_sin_limite, genera 4 informes (más que el plan gratis)
y confirma que ninguno se cobra. También comprueba que un usuario normal sigue limitado y que la IA real
clasifica el caso de prueba de la sección 7.3. Al final borra todo lo creado.

Uso:  python scripts/prueba_sin_limite.py
"""
import hashlib
import random
import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from config import cfg  # noqa: E402
from db import get_db  # noqa: E402
from prueba_integral import API, minuta_sintetica  # noqa: E402

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
resultados = []


def ok(cond, texto):
    resultados.append(bool(cond))
    print(("  OK   " if cond else "  FALLA ") + texto)


def login(email, clave):
    r = httpx.post(f"{cfg.supabase_url}/auth/v1/token?grant_type=password", headers={"apikey": cfg.supabase_anon_key},
                   json={"email": email, "password": clave}, timeout=30)
    r.raise_for_status()
    return httpx.Client(base_url=API, headers={"Authorization": f"Bearer {r.json()['access_token']}"}, timeout=240)


def preparar(cliente, cedula):
    """Sube una minuta con esa cédula (cada cuenta necesita la suya) y registra 4 meses de actividades."""
    obligs = [{"numero": 1, "tipo": "especifica", "texto": "REALIZAR SOPORTE TÉCNICO A LOS EQUIPOS TECNOLÓGICOS, DE "
               "TELECOMUNICACIONES, APLICACIONES Y SISTEMAS DE INFORMACIÓN DE LA DEPENDENCIA"},
              {"numero": 2, "tipo": "especifica", "texto": "ASISTIR A LAS REUNIONES A LAS QUE SE LE CONVOQUE"}]
    hoy = date.today()
    lectura = cliente.post("/contratos/minuta", files={"archivo": ("minuta.docx", minuta_sintetica(cedula), DOCX)})
    lectura.raise_for_status()
    r = cliente.post("/contratos", json={
        "lectura_id": lectura.json()["lectura_id"],
        "contrato": {"numero_contrato": "PRUEBA-1", "objeto": "Apoyo a la gestión", "supervisor_nombre": "SUPERVISOR",
                     "fecha_inicio": (hoy - timedelta(days=150)).isoformat(),
                     "fecha_fin": (hoy + timedelta(days=60)).isoformat()},
        "contratista": {"nombre": "PERSONA DE PRUEBA", "cedula": cedula}, "obligaciones": obligs})
    r.raise_for_status()
    o1 = next(o for o in r.json()["obligaciones"] if o["numero"] == 1)
    informes = []
    for i in range(4):
        dia = (hoy.replace(day=1) - timedelta(days=31 * i)).replace(day=10)
        cliente.post("/actividades", json={"fecha": dia.isoformat(), "texto_original": "mantenimiento",
                                           "texto_redactado": "Realicé mantenimiento.", "obligacion_id": o1["id"],
                                           "estado": "confirmada"}).raise_for_status()
        informes.append(cliente.get("/informes/actual", params={"periodo": dia.strftime("%Y-%m")}).json()["informe"]["id"])
    return informes


def main():
    db = get_db()
    creados = []
    clave = "Clave-Prueba-123"
    cedulas = [str(random.randint(1_100_000_000, 1_199_999_999)) for _ in range(2)]
    try:
        email_libre = f"pruebas.libre.{secrets.token_hex(3)}@example.com"
        email_normal = f"pruebas.normal.{secrets.token_hex(3)}@example.com"
        for email in (email_libre, email_normal):
            creados.append((db.crear_usuario(email, clave, "Prueba")["id"], email))
        db.insertar("cuentas_sin_limite", {"email": email_libre, "nota": "prueba automática"})

        print("Cuenta sin límite")
        libre = login(email_libre, clave)
        s = libre.get("/suscripcion/actual").json()
        ok(s.get("sin_limite") and s["limite"] is None, f"suscripción: plan={s['plan']} límite={s['limite']}")
        informes = preparar(libre, cedulas[0])
        cobrados = []
        for inf in informes:
            r = libre.post(f"/informes/{inf}/generar", json={"tipo": "parcial"})
            cobrados.append((r.status_code, r.json().get("cobrado")))
        ok(all(c == (200, False) for c in cobrados), f"4 informes generados sin cobrar: {cobrados}")
        usados = db.select("consumo_informes", {"user_id": creados[0][0]})
        ok(not usados, "no quedó consumo registrado")
        r = libre.post("/actividades/clasificar", json={"texto": "Hoy realicé mantenimiento a los computadores de la oficina",
                                                         "fecha": date.today().isoformat()})
        d = r.json()
        a = (d.get("asignaciones") or [{}])[0]
        ok(r.status_code == 200 and a.get("obligacion_numero") == 1 and a.get("confianza", 0) >= 0.75,
           f"IA real: obligación {a.get('obligacion_numero')} con {a.get('confianza')} ({d.get('modelo')}) -> "
           f"«{a.get('redaccion')}»")

        print("Cuenta normal (debe seguir limitada)")
        normal = login(email_normal, clave)
        informes = preparar(normal, cedulas[1])
        codigos = [normal.post(f"/informes/{inf}/generar", json={"tipo": "parcial"}).status_code for inf in informes[:2]]
        ok(codigos == [200, 402], f"gratis: 1 informe y el segundo 402 -> {codigos}")
    finally:
        print("Limpieza")
        for uid, email in creados:
            try:
                db.borrar("cuentas_sin_limite", {"email": email})
            except Exception:
                pass
            try:
                login(email, clave).delete("/cuenta")
            except Exception:
                db.borrar_usuario(uid)
        for c in cedulas:
            db.borrar("pruebas_gratis", {"cedula_hash": hashlib.sha256(c.encode()).hexdigest()})
        print("  usuarios de prueba eliminados")
    print(f"\n{sum(resultados)}/{len(resultados)} verificaciones OK")
    sys.exit(0 if all(resultados) else 1)


if __name__ == "__main__":
    main()
