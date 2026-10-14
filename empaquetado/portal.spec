# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: programa de escritorio en una carpeta (onedir), listo para Inno Setup.
# Uso (desde la carpeta empaquetado):  pyinstaller portal.spec --noconfirm --workpath %TEMP%\portal_build
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

ESCRITORIO = Path(SPECPATH).parent / "escritorio"

datas = [
    (str(ESCRITORIO / "recursos"), "recursos"),
    (str(ESCRITORIO / ".env"), "."),          # solo valores públicos: URL de la API, URL de Supabase y llave anon
]
datas += collect_data_files("qtawesome")      # fuentes de íconos
datas += copy_metadata("keyring")             # keyring descubre el backend de Windows por metadatos

a = Analysis(
    [str(ESCRITORIO / "main.py")],
    pathex=[str(ESCRITORIO)],
    binaries=[],
    datas=datas,
    hiddenimports=["keyring.backends.Windows", "win32ctypes.core", "win32ctypes.pywin32"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pandas", "numpy", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "pytest", "respx"],
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
