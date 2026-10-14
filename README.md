# Portal del Trabajador · Informes de actividades

Programa de escritorio para Windows (PySide6) con el que contratistas y practicantes redactan su informe
mensual de actividades a partir de frases simples. La IA (vía OpenRouter) ubica cada actividad en la
obligación del contrato y la redacta en tono formal; al final se llena la plantilla oficial
**GDOGC01-F007** sin cambiar su formato y se entrega en Word y PDF.

```
portal-trabajador/
├── backend/        API en JSON (FastAPI). Guarda las llaves, cobra el cupo y genera el informe
│   ├── .env            ← SECRETOS (Supabase, OpenRouter, Wompi). Aquí va tu llave de OpenRouter
│   ├── providers.json  ← modelos de IA en orden de respaldo
│   ├── plantillas_base/GDOGC01-F007.docx   plantilla oficial en blanco
│   ├── routers/ servicios/ scripts/ tests/
├── escritorio/     programa para PC (PySide6, sin HTML)
│   ├── .env            ← solo valores públicos: dirección del backend y de Supabase
│   ├── app/ (ventanas, widgets, servicios, tema.py) · recursos/ · tests/
├── supabase/schema.sql   tablas, RLS, buckets, planes y funciones de cupo/pago
├── empaquetado/          portal.spec (PyInstaller), instalador.iss (Inno Setup), construir.bat
├── render.yaml           servidor en la nube (Render)
└── DESPLIEGUE.md         ← paso a paso para subir el backend a la nube, Wompi y Supabase
```

**Para repartir el programa a muchas personas:** el backend va en la nube y cada programa se conecta a él.
Sigue [DESPLIEGUE.md](DESPLIEGUE.md).

## 1. Lo que ya quedó configurado

- **Supabase** (proyecto `yzzfplbhnyexczxnselo`): se ejecutó `supabase/schema.sql` (12 tablas con RLS, 4 buckets
  privados, planes Gratis/Normal/Pro y las funciones `consumir_informe`, `estado_suscripcion` y `procesar_pago`).
- **Plantilla oficial** publicada como plantilla global (todos los usuarios la usan por defecto).
- **backend/.env** con la URL y las llaves de Supabase y la llave de OpenRouter. Faltan las de Wompi.
- **Cuenta de pruebas sin límite:** `samuelolimiranda@gmail.com` (ver sección 2b).

## 2. Llave y modelos de OpenRouter

1. Las llaves van en `backend/.env` (en la nube, en Render): `OPENROUTER_API_KEYS=sk-or-...,sk-or-...`
   (se sacan en https://openrouter.ai/keys). Se puede poner una o varias separadas por coma: si una se queda sin
   saldo, es inválida o tiene límite, el backend pasa sola a la siguiente y la vuelve a probar más tarde.
2. Los modelos están en `backend/providers.json`. Se prueban de arriba hacia abajo; si uno falla
   (error, demora o JSON inválido) pasa al siguiente. `"enabled": false` desactiva uno.
3. Después de cambiar las llaves o los modelos, reinicia el backend. `http://127.0.0.1:8000/api/health`
   debe decir `"ia_configurada": true` y `"ia_llaves": {"total": N, "disponibles": N}`.

Probados con el caso de la especificación ("Hoy realicé mantenimiento a los computadores de la oficina"):
DeepSeek V4.1 Flash y GPT Luna lo ubican en la obligación 1 con confianza alta (80 %–95 %), sin agregar datos.

Sin llave el programa igual funciona: la minuta se lee con reglas (salen las 10 obligaciones) y las
actividades se ubican a mano.

## 2a. Redacción, anexos e imágenes

- **Redacción:** la IA ubica la actividad en su obligación y la reescribe en lenguaje administrativo formal
  (1 o 2 oraciones, vocabulario técnico, vínculo con la obligación usando sus propias palabras), sin agregar
  hechos, cifras, nombres ni resultados que el trabajador no escribió.
- **Anexos:** al adjuntar una evidencia, la IA escribe su descripción según la actividad y la obligación
  ("Registro fotográfico de…", "Documento soporte de…", "Archivo de soporte de…"). En la tabla de ejecución la
  actividad termina con "Se adjunta como evidencia el Anexo N: …" y la lista ANEXOS del informe usa esa
  descripción. Se puede editar o volver a pedir a la IA en *Mi informe → Editar actividad*.
- **Copia local:** cada evidencia elegida se copia a `Documentos\Portal del Trabajador\Evidencias\AAAA-MM\`
  (botón "Abrir carpeta de evidencias") y desde ahí se sube.
- **Fotos en el informe:** las imágenes (JPG/PNG) se pegan al final del Word, después del cuadro
  "VALIDACIÓN DEL DOCUMENTO", en una página nueva titulada "REGISTRO FOTOGRÁFICO DE LOS ANEXOS", dos por página,
  cada una con "Anexo N. descripción". Se enderezan y se reducen para que el archivo no pese de más. Los PDF,
  Word y Excel quedan listados en ANEXOS como archivo adjunto.

## 2b. Cuentas de prueba sin límite

Las cuentas de la tabla `cuentas_sin_limite` generan informes sin cupo y sin límite de solicitudes por
hora (útil para probar). La regla la aplica la base de datos, así que no se puede activar modificando el
programa, y solo vale si el correo está confirmado en Supabase. El programa muestra
"Cuenta de pruebas · sin límite".

```sql
-- Agregar una cuenta (en el SQL Editor de Supabase)
insert into public.cuentas_sin_limite (email, nota) values ('correo@ejemplo.com', 'pruebas');
-- Quitarla
delete from public.cuentas_sin_limite where email = 'correo@ejemplo.com';
```

Prueba automática: `python scripts/prueba_sin_limite.py` (con el backend encendido).

## 3. Correr en VS Code (desarrollo)

**Lo más fácil:** doble clic en `iniciar_todo.bat` (en la carpeta `portal-trabajador`).

Con `MODO_BACKEND=remoto` (en `escritorio/.env`, así viene) el programa usa el servidor de Render
(`API_BASE_URL=https://portal-trabajador-api.onrender.com`). Si el servidor estaba apagado (plan gratis), la
pantalla de carga lo explica y espera; mientras el programa está abierto lo mantiene encendido.

Con `MODO_BACKEND=integrado` y `API_BASE_URL=http://127.0.0.1:8000` el programa **enciende el backend por
dentro** al abrirse y lo apaga al cerrarse (solo pruebas en este PC). El servidor interno solo escucha en
`127.0.0.1` y usa las llaves de `backend/.env`. Si el puerto 8000 está ocupado, usa otro libre.

Requiere Python 3.11 o superior.

```powershell
# Terminal 1: backend
cd backend
pip install -r requirements-dev.txt   # el servidor usa requirements.txt; -dev agrega las herramientas de prueba
python main.py                 # o doble clic en iniciar_backend.bat

# Terminal 2: programa
cd escritorio
pip install -r requirements.txt
python main.py                 # o doble clic en iniciar_programa.bat
```

El programa busca el backend en `API_BASE_URL` (archivo `escritorio/.env`, por defecto `http://127.0.0.1:8000`).

## 4. Pruebas

```powershell
cd backend;    python -m pytest          # 53 pruebas: minuta, IA con varias llaves, cédulas, generador, Wompi, API, configuración
cd escritorio; python -m pytest          # 32 pruebas: propuesta de la IA, cliente, tema (contraste AA), widgets, https, instalador
# De punta a punta contra Supabase real (con el backend encendido): crea usuarios, recorre todo y los borra
cd backend;    python scripts/prueba_integral.py "ruta\de\una\minuta.pdf"   # 40 verificaciones
cd backend;    python scripts/prueba_sin_limite.py                           # cuentas de prueba sin límite
```

`prueba_integral.py` comprueba, entre otras cosas: una cédula = una cuenta (otra cuenta no puede registrar la
misma minuta), la cédula debe estar en la minuta y no se puede cambiar, borrar la cuenta no da otra prueba
gratis, nadie puede escribir directo en la base de datos ni en el almacenamiento, y ningún usuario ve datos de otro.

## 5. Ajustes pendientes en el panel de Supabase

1. **Recuperar contraseña con código.** El programa pide el código que llega al correo. En
   *Authentication → Email Templates → Reset Password* agrega el código al mensaje, por ejemplo:
   `<p>Tu código para cambiar la contraseña es: <b>{{ .Token }}</b></p>`
2. **Confirmación de correo.** Viene activada: al registrarse, el usuario debe abrir el enlace del correo antes
   de entrar. En *Authentication → URL Configuration* cambia el *Site URL* (hoy `localhost:3000`) por
   `https://TU-SERVIDOR/confirmado`: el backend muestra ahí "Tu correo quedó confirmado, vuelve al programa".
3. **Correo propio (SMTP).** El correo de Supabase gratis permite muy pocos envíos por hora. Para usuarios
   reales configura un SMTP en *Authentication → SMTP Settings*.
4. Cambia la contraseña de la base de datos y rota la llave secreta (`sb_secret_…`) antes de salir a
   producción: ambas se compartieron en el chat de desarrollo. Si rotas la llave, actualiza `backend/.env`.

## 6. Pagos con Wompi

Dónde están las 4 llaves en el panel de Wompi, la URL de eventos y las tarjetas de prueba:
[DESPLIEGUE.md, paso 4](DESPLIEGUE.md#paso-4-wompi-dónde-están-las-variables).

Mientras el backend corra en este PC, Wompi no puede llamar al webhook. Por eso el botón
**"Ya pagué, verificar"** (y la consulta automática cada 3 s) le pregunta a Wompi por la referencia
usando la llave privada, y aplica el resultado con las mismas validaciones (referencia, monto, una sola vez).

## 7. Empaquetar el instalador (después de terminar las pruebas)

```powershell
cd empaquetado
construir.bat
```

Crea el ejecutable con PyInstaller (en `%LOCALAPPDATA%\PortalTrabajador-build`, fuera de OneDrive), lo verifica
con `PortalTrabajador.exe --verificar` y arma el instalador con Inno Setup en `empaquetado\salida\`.
El instalador no pide permisos de administrador (se instala para el usuario). Para evitar la alerta de
SmartScreen, firma el instalador con un certificado de firma de código (ver comentarios en `instalador.iss`).

Antes de repartir el instalador, pon `MODO_BACKEND=remoto` y la dirección https del servidor en
`API_BASE_URL` (`escritorio/.env`). `construir.bat` no crea el instalador si el programa apunta a un servidor
local, sin https, o si `escritorio/.env` tiene alguna llave secreta. También se puede poner un `.env` junto a
`PortalTrabajador.exe` instalado para cambiar la dirección sin reinstalar.

## 8. ¿Backend integrado o servidor? (decidir antes de repartir el instalador)

- **Integrado** (como está ahora): sirve para este PC o PCs que tú controlas. Las llaves (la secreta de
  Supabase, OpenRouter y Wompi) tienen que estar en cada PC, así que **no sirve para repartirlo a otros
  trabajadores**: cualquiera podría sacar la llave secreta de Supabase y ver los datos de todos (nombres,
  cédulas, contratos), gastar tu saldo de OpenRouter o saltarse los planes.
- **Servidor** (para repartirlo): el backend corre en un solo lugar (un PC o servidor de la oficina que quede
  encendido, o un servicio en la nube) y los programas se conectan con `MODO_BACKEND=remoto`. Las llaves nunca
  salen de ese servidor.

## 8b. Subir el backend a la nube

Paso a paso en [DESPLIEGUE.md](DESPLIEGUE.md) (GitHub privado + Render con `render.yaml`). `backend/Dockerfile`
instala LibreOffice y fuentes con las mismas medidas de la plantilla (Liberation Sans = Arial, Liberation Sans
Narrow = Arial Narrow, Carlito = Calibri), corre sin permisos de administrador y con versiones fijas. Las llaves
se escriben en el panel de Render, nunca en el repositorio.

## 9. Decisiones que difieren de la especificación

| Tema | Especificación | Lo que se hizo y por qué |
|---|---|---|
| Modelos de IA | `OPENROUTER_MODELS` | `backend/providers.json` (mismo formato de ACTIVI-VALO); `OPENROUTER_MODELS` queda de respaldo |
| Acceso a Supabase desde el PC | supabase-py | API REST de Supabase con httpx: mismo resultado, menos peso en el .exe y compatible con las llaves nuevas `sb_publishable_` |
| Validar el JWT | `SUPABASE_JWT_SECRET` | Se consulta a Supabase Auth (sirve con cualquier tipo de firma); queda en caché 5 min |
| Tema | pyqtdarktheme / qt-material | QSS propio generado desde `tema.py` (pyqtdarktheme no instala en Python 3.12) |
| Colores | verde azulado `#0A3D3D`, fondo crema | A pedido: paleta más profesional (azul petróleo `#0E5A6B`, grises fríos, barra lateral azul marino), radio de 6 px, indicadores en Inicio y acceso en dos columnas. Todos los pares cumplen contraste AA (lo comprueba `tests/test_tema.py`) |
| Cupo | 2 / 2 por mes / ilimitado | Además, cuentas de prueba sin límite (`cuentas_sin_limite`) |
| Fecha del contrato | no estaba en la tabla | Columna `contratos.fecha_contrato`, porque la plantilla la pide |
| Seguridad del perfil | política "for all" | El usuario solo puede editar su nombre (no su `rol` ni su cédula) |
| Escritura en la base de datos | políticas "for all" | Con la llave pública el usuario solo LEE sus filas; contratos, obligaciones, informes, actividades, evidencias y archivos solo los escribe el backend (que valida cédula, cupo y archivos) |
| Cédula | campo del perfil | Una cédula = una cuenta: debe aparecer en la minuta (el texto queda en el servidor), se vincula al guardar el primer contrato y no se puede cambiar. La prueba gratis se cuenta por cédula (huella SHA-256), así que borrar la cuenta no da otra |
| Llaves de OpenRouter | una (`OPENROUTER_API_KEY`) | Varias (`OPENROUTER_API_KEYS`) con cambio automático si una falla; la anterior sigue funcionando |
| Límite por usuario | en memoria | En la base de datos (`registrar_solicitud`): vale para todos los procesos del servidor y no se reinicia |
| Ciclo mensual | `now()` | Hora de Colombia (`America/Bogota`), para que el mes no cambie 5 horas antes |
| Activación del pago | en el webhook | Función SQL atómica `procesar_pago` (idempotente) + consulta a Wompi con llave privada como respaldo del webhook |
| Plantilla en PDF (8.3) | alternativa con PyMuPDF | No se implementó: la plantilla oficial está en Word. Se pide la versión .docx |
| Endpoints agregados | — | `PUT /api/contratos/{id}`, `DELETE /api/actividades/{id}`, evidencias (`POST/DELETE`), `GET/DELETE /api/plantillas…`, `POST /api/plantillas/{id}/confirmar`, `DELETE /api/cuenta` (Ley 1581) |
| Escudo en el inicio de sesión | `[escudo]` | Ícono neutro: el producto es de pago y el escudo daría a entender que es oficial. El informe sí lleva el escudo porque es parte de la plantilla |

## 10. Problemas comunes

- **"No pudimos conectarnos con el servidor"**: el backend está apagado o `API_BASE_URL` está mal.
- **"No pudimos analizar esto ahora"**: falta la llave de OpenRouter, no hay saldo o los nombres de modelo de
  `providers.json` no existen. La actividad se puede guardar sin clasificar.
- **No sale el PDF**: el backend necesita Word (en Windows) o LibreOffice. El Word del informe sí se entrega.
- **La fecha del contrato sale en negrita**: así viene esa celda en la plantilla oficial; el programa respeta
  el formato de cada celda.
- Registro del programa: `%LOCALAPPDATA%\PortalTrabajador\Logs\portal.log`.
