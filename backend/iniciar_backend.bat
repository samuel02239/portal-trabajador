@echo off
rem Enciende el backend en http://127.0.0.1:8000 (deja esta ventana abierta mientras usas el programa).
cd /d "%~dp0"
python -m pip install --disable-pip-version-check -q -r requirements.txt
python main.py
pause
