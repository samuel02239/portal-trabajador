@echo off
rem Construye el .exe (PyInstaller) y, si Inno Setup está instalado, el instalador.
rem Uso: doble clic o "construir.bat" desde esta carpeta.
rem Los archivos intermedios van a %LOCALAPPDATA%\PortalTrabajador-build para no llenar OneDrive;
rem el instalador final queda en empaquetado\salida\.
setlocal
cd /d "%~dp0"
set "BUILD=%LOCALAPPDATA%\PortalTrabajador-build"
set "DIST=%BUILD%\dist\PortalTrabajador"

echo [1/4] Instalando dependencias del programa...
python -m pip install --disable-pip-version-check -q -r ..\escritorio\requirements.txt || goto :error
rem El instalador que se reparte debe usar el servidor en la nube (remoto + https) y solo la llave publica
python ..\escritorio\scripts\revisar_distribucion.py || goto :error

echo [2/4] Preparando icono y hoja de estilo...
pushd ..\escritorio
if not exist recursos\icono.ico python scripts\crear_icono.py || goto :error
python -m app.tema || goto :error
popd

echo [3/4] Creando el ejecutable con PyInstaller (tarda unos minutos)...
python -m PyInstaller portal.spec --noconfirm --clean --workpath "%BUILD%\work" --distpath "%BUILD%\dist" || goto :error
start "" /wait "%DIST%\PortalTrabajador.exe" --verificar
if errorlevel 1 (
  echo La verificacion del ejecutable fallo. Revisa %LOCALAPPDATA%\PortalTrabajador\Logs\portal.log
  goto :error
)
echo Ejecutable verificado: %DIST%\PortalTrabajador.exe

echo [4/4] Creando el instalador con Inno Setup...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo No se encontro Inno Setup 6. Instalalo con:  winget install --id JRSoftware.InnoSetup -e
  goto :fin
)
"%ISCC%" /Q "/DDist=%DIST%" instalador.iss || goto :error
echo Instalador listo en empaquetado\salida\

:fin
endlocal
exit /b 0

:error
echo.
echo Hubo un error. Revisa los mensajes de arriba.
endlocal
exit /b 1
