"""Conversión DOCX -> PDF.

1. LibreOffice headless (soffice --headless --convert-to pdf), como en el servidor.
2. En Windows sin LibreOffice: el Microsoft Word instalado, por automatización COM.
Si ninguno está disponible, se entrega solo el DOCX.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from config import cfg

log = logging.getLogger("portal.pdf")
_LOCK = threading.Lock()  # una conversión a la vez (Word y soffice no toleran bien instancias paralelas)

_RUTAS_SOFFICE = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice", "/usr/lib/libreoffice/program/soffice", "/opt/libreoffice/program/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]

_SCRIPT_WORD = r"""
param([string]$Entrada, [string]$Salida)
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
  $doc = $word.Documents.Open($Entrada, $false, $true)
  $doc.SaveAs([ref]$Salida, [ref]17)
  $doc.Close([ref]0)
} finally {
  $word.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
"""


def _soffice() -> str | None:
    if cfg.libreoffice_path and Path(cfg.libreoffice_path).exists():
        return cfg.libreoffice_path
    for nombre in ("soffice", "libreoffice"):
        encontrado = shutil.which(nombre)
        if encontrado:
            return encontrado
    return next((r for r in _RUTAS_SOFFICE if Path(r).exists()), None)


def _word_disponible() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CurVer"))
        return True
    except OSError:
        return False


def motor() -> str | None:
    """'libreoffice', 'word' o None."""
    if _soffice():
        return "libreoffice"
    if _word_disponible():
        return "word"
    return None


def convertir(docx: bytes, timeout: int = 180, extension: str = "docx") -> bytes | None:
    """Devuelve el PDF o None si no hay con qué convertir o la conversión falla.

    extension: 'docx' (informe y evidencias Word) o 'xlsx' (evidencias de Excel; solo con LibreOffice).
    """
    eleccion = motor()
    if eleccion == "word" and extension != "docx":
        eleccion = None
    if not eleccion:
        log.warning("No hay LibreOffice ni Word para convertir a PDF.")
        return None
    with _LOCK, tempfile.TemporaryDirectory(prefix="portal_pdf_") as carpeta:
        entrada = Path(carpeta) / f"informe.{extension}"
        salida = Path(carpeta) / "informe.pdf"
        entrada.write_bytes(docx)
        try:
            if eleccion == "libreoffice":
                # Perfil de LibreOffice reutilizado por proceso: la primera conversión lo crea y las demás son
                # más rápidas. Cada proceso usa el suyo, así que dos trabajadores no se estorban.
                perfil = Path(tempfile.gettempdir()) / f"portal_lo_{os.getpid()}"
                subprocess.run([_soffice(), f"-env:UserInstallation={perfil.as_uri()}", "--headless",
                                "--norestore", "--convert-to", "pdf", "--outdir", carpeta, str(entrada)],
                               check=True, timeout=timeout, capture_output=True)
            else:
                script = Path(carpeta) / "convertir.ps1"
                script.write_text(_SCRIPT_WORD, encoding="utf-8-sig")
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                "-File", str(script), str(entrada), str(salida)],
                               check=True, timeout=timeout, capture_output=True, creationflags=flags)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            detalle = getattr(exc, "stderr", b"") or b""
            log.warning("Falló la conversión a PDF con %s: %s %s", eleccion, type(exc).__name__,
                        detalle[:300].decode(errors="ignore") if isinstance(detalle, bytes) else detalle)
            return None
        return salida.read_bytes() if salida.exists() else None


if __name__ == "__main__":  # prueba manual: python -m servicios.conversor_pdf archivo.docx
    origen = Path(sys.argv[1])
    pdf = convertir(origen.read_bytes())
    print("motor:", motor(), "| pdf:", len(pdf) if pdf else None)
    if pdf:
        origen.with_suffix(".pdf").write_bytes(pdf)
        os.startfile(origen.with_suffix(".pdf")) if sys.platform == "win32" else None
