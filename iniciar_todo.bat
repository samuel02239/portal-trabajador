@echo off
rem Abre el Portal del Trabajador en este PC.
rem Con MODO_BACKEND=integrado (escritorio\.env) el programa enciende su servidor por dentro: no hace falta
rem ninguna ventana negra. Con MODO_BACKEND=remoto usa el servidor de API_BASE_URL.
start "" /D "%~dp0escritorio" pythonw main.py
