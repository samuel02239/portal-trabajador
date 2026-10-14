# -*- mode: python ; coding: utf-8 -*-
# PyInstaller · versión PERSONAL para pruebas: el backend va DENTRO del programa (MODO_BACKEND=integrado).
# Al abrirse, el programa enciende su servidor interno en 127.0.0.1 y lo apaga al cerrarse.
# Las llaves NO van en el paquete: construir_personal.bat copia backend/.env a
# %LOCALAPPDATA%\PortalTrabajador\backend.env (solo en este PC).
# Para repartir a otras personas se usa portal.spec + servidor en la nube (DESPLIEGUE.md).
import ast
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

ESCRITORIO = Path(SPECPATH).parent / "escritorio"
BACKEND = Path(SPECPATH).parent / "backend"
NO_EMPACAR = {"tests", "scripts", "__pycache__", ".pytest_cache"}


def archivos_backend():
    """Código del backend, providers.json y la plantilla base. Nunca .env."""
    salida = []
    for archivo in BACKEND.rglob("*"):
        rel = archivo.relative_to(BACKEND)
        if archivo.is_dir() or NO_EMPACAR & set(rel.parts):
            continue
        if archivo.suffix in (".py", ".json") or rel.parts[0] == "plantillas_base":
            salida.append((str(archivo), str(Path("backend") / rel.parent)))
    return salida


def importaciones_backend():
    """Módulos externos que usa el backend: como se carga desde el código fuente, PyInstaller no los ve solo."""
    locales = {p.stem for p in BACKEND.glob("*.py")} | {d.name for d in BACKEND.iterdir()
                                                       if (d / "__init__.py").exists()}
    externos = set()
    for archivo in BACKEND.rglob("*.py"):
        if NO_EMPACAR & set(archivo.relative_to(BACKEND).parts):
            continue
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.Import):
                nombres = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
                nombres = [nodo.module] + [f"{nodo.module}.{a.name}" for a in nodo.names]
            else:
                continue
            externos.update(n for n in nombres if n.split(".")[0] not in locales and n != "__future__")
    return sorted(externos)


hidden = ["keyring.backends.Windows", "win32ctypes.core", "win32ctypes.pywin32"]
hidden += importaciones_backend()
for paquete in ("uvicorn", "fastapi", "starlette", "pydantic", "pdfplumber", "pdfminer", "pypdfium2",
                "pypdfium2_raw", "docx", "python_multipart", "multipart", "anyio", "h11", "httptools", "websockets"):
    hidden += collect_submodules(paquete)

def env_integrado() -> str:
    """Copia de escritorio/.env (solo valores públicos) forzada a modo integrado, sin importar cómo esté el original."""
    lineas = [l for l in (ESCRITORIO / ".env").read_text(encoding="utf-8").splitlines()
              if not l.startswith(("MODO_BACKEND=", "API_BASE_URL="))]
    lineas += ["MODO_BACKEND=integrado", "API_BASE_URL=http://127.0.0.1:8000"]
    carpeta = Path(workpath) / "env_personal"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / ".env").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return str(carpeta / ".env")


datas = [
    (str(ESCRITORIO / "recursos"), "recursos"),
    (env_integrado(), "."),
]
datas += archivos_backend()
datas += collect_data_files("qtawesome")
datas += copy_metadata("keyring")
for paquete in ("pdfminer", "docx", "pypdfium2", "pypdfium2_raw", "certifi"):
    datas += collect_data_files(paquete)
binaries = collect_dynamic_libs("pypdfium2_raw")

a = Analysis(
    [str(ESCRITORIO / "main.py")],
    pathex=[str(ESCRITORIO)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pandas", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "pytest", "respx",
              "psycopg"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PortalTrabajador",
    icon=str(ESCRITORIO / "recursos" / "icono.ico"),
    console=False,
    version=None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PortalTrabajador")
