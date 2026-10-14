# Subir el backend a la nube (Render) y dejarlo listo para muchos usuarios

```
 PC de cada trabajador                Servidor en la nube (Render)              Servicios
 ┌──────────────────────┐   https    ┌───────────────────────────────┐    ┌──────────────────────────┐
 │ Portal del Trabajador│ ─────────► │ backend (FastAPI + LibreOffice)│ ─► │ Supabase: datos, archivos│
 │ solo llave PÚBLICA   │            │ TODAS las llaves secretas      │ ─► │ OpenRouter: IA (varias   │
 └──────────────────────┘            └───────────────────────────────┘    │   llaves con respaldo)   │
                                             ▲                            │ Wompi: pagos             │
                                             └──── aviso de pago ─────────┴──────────────────────────┘
```

Las llaves secretas (Supabase secreta, OpenRouter y Wompi) viven **solo en Render**. El instalador que se
reparte lleva únicamente la dirección del servidor y la llave pública de Supabase.

Tiempo estimado: 1 hora la primera vez.

---

## Paso 0. Cambiar las llaves que se compartieron en el chat

La contraseña de la base de datos, la llave secreta de Supabase y la llave de OpenRouter se escribieron en el
chat de desarrollo. Antes de tener usuarios reales, créalas de nuevo:

| Qué | Dónde |
|---|---|
| Contraseña de la base de datos | Supabase → *Project Settings → Database → Reset database password* |
| Llave secreta `sb_secret_…` | Supabase → *Project Settings → API Keys → Secret keys*: crea una nueva y borra la anterior |
| Llave de OpenRouter | https://openrouter.ai/keys: crea una nueva y borra la anterior (puedes crear 2 o 3, ver paso 2) |

Pon las nuevas también en `backend/.env` de tu PC para seguir haciendo pruebas.

---

## Paso 1. Subir el código a GitHub (repositorio privado)

La carpeta `portal-trabajador` ya es un repositorio de Git (Git quedó instalado para tu usuario). `.gitignore`
deja por fuera `backend/.env`, los instaladores y los PDF; antes del primer envío se revisó que no viaje ninguna llave.

1. Entra a https://github.com/new con tu cuenta.
2. *Repository name*: `portal-trabajador`. Marca **Private**. **No** marques README, .gitignore ni licencia.
3. Pulsa **Create repository** y copia la dirección (`https://github.com/TU-USUARIO/portal-trabajador.git`).
4. Envía el código (desde la carpeta `portal-trabajador`, en PowerShell):

   ```powershell
   git remote add origin https://github.com/TU-USUARIO/portal-trabajador.git
   git push -u origin main
   ```

   La primera vez se abre una ventana de GitHub para que inicies sesión **en tu navegador** (nunca escribas la
   contraseña en la terminal ni en un chat). Queda recordado para los siguientes envíos.

**Enviar cambios después** (Render se actualiza solo con cada envío):

```powershell
git add -A
git commit -m "Describe el cambio"
git push
```

---

## Paso 2. Crear el servidor en Render

1. Entra a https://render.com → **Get Started** → **GitHub** (regístrate con tu cuenta de GitHub y autoriza a Render).
2. En el panel: **New +** → **Blueprint**.
3. En *Connect a repository*, si no aparece `portal-trabajador` (es privado): pulsa **Configure account** /
   *Configure GitHub App* → *Only select repositories* → elige `portal-trabajador` → **Save**. Vuelve y pulsa
   **Connect** junto al repositorio.
4. *Blueprint Name*: `portal-trabajador`. Render lee `render.yaml` y muestra el servicio **portal-trabajador-api**
   (Docker, plan *Free*, región Oregon).
5. Render pide 4 variables. Cópialas de tu `backend/.env` (o de los paneles):

| Variable | De dónde se saca |
|---|---|
| `SUPABASE_URL` | Supabase → *Project Settings → Data API* → Project URL (`https://yzzfplbhnyexczxnselo.supabase.co`) |
| `SUPABASE_ANON_KEY` | Supabase → *Project Settings → API Keys* → **Publishable key** (`sb_publishable_…`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → *Project Settings → API Keys* → **Secret key** (`sb_secret_…`; la nueva si hiciste el paso 0) |
| `OPENROUTER_API_KEYS` | https://openrouter.ai/keys. **Varias separadas por coma**: `sk-or-v1-aaa…,sk-or-v1-bbb…` |

   Las de Wompi no se piden aquí: se agregan después (paso 4). Sin ellas todo funciona y el programa dice que
   los pagos aún no están habilitados.

6. Pulsa **Deploy Blueprint** (o *Apply*). La primera construcción tarda de 5 a 15 minutos (instala LibreOffice);
   puedes verla en el servicio → **Logs**.
5. Cuando el servicio diga **Live**, copia su dirección (arriba, algo como `https://portal-trabajador-api.onrender.com`;
   si el nombre estaba ocupado, Render le agrega letras). Ábrela en el navegador agregando `/api/health`. Debe decir:

```json
"ok": true, "supabase": true, "ia_configurada": true, "ia_llaves": {"total": 2, "disponibles": 2},
"pdf": "libreoffice", "avisos_configuracion": []
```

Si `avisos_configuracion` no está vacío, dice exactamente qué variable corregir (nunca muestra su valor).

**Varias llaves de OpenRouter:** el servidor usa la primera; si una se queda sin saldo (402), es inválida (401/403)
o tiene límite (429), pasa sola a la siguiente y la vuelve a probar más tarde (30 s si es por límite, 15 min si es
por saldo, 1 hora si es inválida). En `/api/health`, `"disponibles"` menor que `"total"` significa que alguna está
pausada: revisa su saldo en OpenRouter. En la tabla `ia_logs` de Supabase, la columna `llave` muestra los últimos
5 caracteres de la llave que se usó en cada solicitud.

**Plan y costo** (verifica el precio actual en render.com/pricing):
- *Free* (el de `render.yaml`, para pruebas): se apaga tras 15 min sin uso. Al abrir el programa después de un
  rato verás "Conectando con el servidor…" hasta un minuto mientras despierta; el PDF tarda más. El aviso de
  pago de Wompi puede perderse si llega dormido: usa el botón "Ya pagué, verificar".
- *Starter* (≈ US$7/mes): para usuarios reales. No se apaga. Cambia `plan: free` por `plan: starter` en
  `render.yaml` y envía el cambio (o en Render → servicio → *Settings → Instance Type*).
- Con muchos usuarios a la vez (por ejemplo, fin de mes): *Standard* (2 GB) y `WEB_CONCURRENCY` en `2`.

---

## Paso 3. Conectar el programa al servidor y probar

Usa la dirección exacta del paso 2 en estas dos líneas:

```
MODO_BACKEND=remoto
API_BASE_URL=https://portal-trabajador-api.onrender.com
```

- **Programa instalado** (`PortalTrabajador-Personal`): crea un archivo llamado `.env` con esas dos líneas en la
  carpeta del programa (`%LOCALAPPDATA%\Programs\PortalTrabajador`, junto a `PortalTrabajador.exe`). Al abrirlo usa
  el servidor. Para volver al servidor interno, borra ese `.env`.
- **Desde el código** (`iniciar_todo.bat`): cambia esas dos líneas en `escritorio/.env`. Para volver, pon
  `MODO_BACKEND=integrado` y `API_BASE_URL=http://127.0.0.1:8000`.

Prueba todo: iniciar sesión, cargar la minuta, registrar actividades con fotos, generar el informe y descargar
Word y PDF. Los datos son los mismos en los dos modos (es la misma base de datos de Supabase).

---

## Paso 4. Wompi: dónde están las variables

1. Entra a https://comercios.wompi.co con tu cuenta de comercio.
2. Ve a **Desarrolladores**. Arriba elige el ambiente **Pruebas (Sandbox)**; producción se hace al final.
3. Copia estos 4 valores:

| En Wompi aparece como | Variable en Render | Empieza por (pruebas → producción) |
|---|---|---|
| Llaves del API → **Llave pública** | `WOMPI_PUBLIC_KEY` | `pub_test_` → `pub_prod_` |
| Llaves del API → **Llave privada** (botón *mostrar*) | `WOMPI_PRIVATE_KEY` | `prv_test_` → `prv_prod_` |
| Secretos para integración técnica → **Eventos** | `WOMPI_EVENTS_SECRET` | `test_events_` → `prod_events_` |
| Secretos para integración técnica → **Integridad** | `WOMPI_INTEGRITY_SECRET` | `test_integrity_` → `prod_integrity_` |

4. En la misma sección, en **URL de eventos**, escribe: `https://portal-trabajador-api.onrender.com/api/pagos/webhook`
   (con tu dirección del paso 2) y guarda.
5. En Render: servicio → **Environment** → **Add Environment Variable** → agrega las 4 (nombre y valor) →
   **Save, rebuild and deploy**.
   Escríbelos solo ahí (y en `backend/.env` si quieres probar pagos en tu PC). No los mandes por chat ni correo.
6. `/api/health` debe decir `"pagos": true, "pagos_entorno": "sandbox"` y `avisos_configuracion` vacío.

**Probar un pago (modo pruebas):** en el programa, *Planes → Normal → Pagar*. En la página de Wompi:
- Tarjeta aprobada: `4242 4242 4242 4242`, cualquier fecha futura y CVC `123`. Rechazada: `4111 1111 1111 1111`.
- Nequi aprobado: `3991111111`. Rechazado: `3992222222`.

El plan se activa cuando llega el aviso de Wompi; si se demora, el botón **"Ya pagué, verificar"** le pregunta
directamente a Wompi. Cada pago se aplica una sola vez y se verifica la firma, la referencia y el monto.

**Pasar a cobros reales:** Wompi debe aprobar tu comercio (documentos y cuenta bancaria). Después, en
*Desarrolladores* cambia al ambiente **Producción**, copia las 4 llaves de producción a Render, cambia
`WOMPI_ENV` a `production` y pon la misma URL de eventos en producción. Si mezclas llaves de pruebas con
`production` (o al revés), `/api/health` lo avisa.

---

## Paso 5. Supabase para usuarios reales

En el panel de Supabase:

1. *Authentication → URL Configuration*:
   - **Site URL**: `https://portal-trabajador-api.onrender.com/confirmado` (página que dice "Tu correo quedó confirmado, vuelve al programa").
   - Agrega la misma dirección en **Redirect URLs**.
2. *Authentication → Emails → SMTP Settings*: configura un correo propio (por ejemplo Brevo o Resend, que tienen
   plan gratis). El correo incluido en Supabase solo envía unos pocos mensajes por hora: con muchos usuarios
   el registro y la recuperación de contraseña fallarían.
3. *Authentication → Emails → Templates → Reset Password*: agrega el código que pide el programa:
   `<p>Tu código para cambiar la contraseña es: <b>{{ .Token }}</b></p>`
4. **Plan de Supabase:** el plan gratis pausa el proyecto tras 7 días sin uso y no guarda copias de seguridad
   diarias. Para producción conviene el plan *Pro* (≈ US$25/mes).

---

## Paso 6. Crear el instalador (cuando terminen las pruebas)

Con `escritorio/.env` en modo remoto (paso 3), ejecuta `empaquetado\construir.bat`. Antes de empaquetar, revisa
que el programa use el servidor con https y solo la llave pública; si no, se detiene y dice qué corregir.
Sube el instalador a OneDrive o Google Drive y comparte el enlace.

---

## Paso 7. Actualizar el servidor y el programa

- **Cambios de código:** *Commit* y *Push* en GitHub Desktop. Render construye y publica solo, sin cortar el
  servicio (espera a que `/api/health` responda bien antes de cambiar).
- **Cambios en `supabase/schema.sql`:** se aplican desde tu PC con `python scripts\aplicar_schema.py` (carpeta `backend`).
- **Nueva versión del programa que todos deben instalar:** sube `VERSION_MINIMA_ESCRITORIO` en Render (por ejemplo
  `1.2.0`) y pon el enlace en `URL_DESCARGA_ESCRITORIO`. Quien tenga una versión anterior verá un aviso con el enlace.

---

## Qué quedó protegido

- **Llaves:** las secretas solo están en Render. El instalador no se crea si `escritorio/.env` tiene una llave secreta o no usa https.
- **Conexión cifrada:** el programa rechaza un servidor de internet sin `https://`.
- **Datos de cada persona:** cada usuario solo puede leer lo suyo (RLS) y **no puede escribir directo en la base
  de datos ni subir archivos directo al almacenamiento**: todo pasa por el backend, que valida cédula, cupo,
  tipo y tamaño de archivo.
- **Una cédula = una cuenta:** la cédula debe aparecer en la minuta, queda vinculada a la cuenta, no se puede
  cambiar y no se puede registrar en otra cuenta. La prueba gratis es una por cédula: borrar la cuenta y crear otra
  no da informes gratis nuevos.
- **Pagos:** firma de integridad en el checkout; firma, referencia, monto y moneda verificados en cada aviso; cada pago se aplica una sola vez.
- **Abusos:** máximo 300 solicitudes por minuto por IP, archivos de hasta 20 MB, y por usuario y por hora:
  30 consultas a la IA, 15 minutas, 60 descripciones de evidencias y 30 generaciones de informe (el conteo es
  compartido por todo el servidor y no se borra al reiniciar). Las cuentas de pruebas sin límite no tienen estos topes.
- **Servidor:** corre sin permisos de administrador, con versiones fijas de cada librería y sin páginas de documentación públicas.

---

## Soporte: "mi cédula ya está registrada en otra cuenta"

Las minutas de SECOP II son públicas, así que alguien podría registrar la cédula de otra persona. Si alguien
lo reporta, verifica que sea el titular (por ejemplo, que te envíe una foto de su cédula) y en Supabase →
*SQL Editor*:

```sql
-- ¿Qué cuenta tiene la cédula?
select id, email, nombre_completo, created_at from public.profiles where cedula = '1234567890';
-- Liberarla: esa cuenta queda sin cédula y sin contrato activo
update public.contratos set activo = false where user_id = 'ID-DE-ESA-CUENTA';
update public.profiles set cedula = null where id = 'ID-DE-ESA-CUENTA';
```

Después, el titular carga su minuta en su propia cuenta.

---

## Problemas comunes

| Síntoma | Qué revisar |
|---|---|
| La construcción falla en Render | Pestaña **Logs** del servicio; el error de Docker dice qué faltó |
| `/api/health` muestra avisos | Corrige la variable que nombra en *Environment* y guarda |
| `"ia_configurada": false` o `"disponibles": 0` | Llaves de OpenRouter mal copiadas o sin saldo |
| `"pdf": null` | LibreOffice no quedó instalado: revisa los Logs de la construcción |
| Pago aprobado pero el plan no cambia | URL de eventos en Wompi y `WOMPI_EVENTS_SECRET`; el botón "Ya pagué, verificar" usa la llave privada como respaldo |
| "No pudimos conectarnos con el servidor" | `API_BASE_URL` en `escritorio/.env` y que el servicio esté *Live* en Render |
| Al registrarse no llega el correo | SMTP propio en Supabase (paso 5.2) |
