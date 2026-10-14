@echo off
rem Programa PERSONAL para el periodo de pruebas (solo este PC): el backend va DENTRO del programa.
rem Las llaves de backend\.env se copian a %LOCALAPPDATA%\PortalTrabajador\backend.env (nunca dentro del instalador).
rem Para repartir a otras personas se usa construir.bat con el servidor en la nube (DESPLIEGUE.md).
setlocal
cd /d "%~dp0"
set "BUILD=%LOCALAPPDATA%\PortalTrabajador-build-personal"
set "DIST=%BUILD%\dist\PortalTrabajador"
set "LLAVES=%LOCALAPPDATA%\PortalTrabajador\backend.env"

echo [1/5] Instalando dependencias del programa y del backend...
python -m pip install --disable-pip-version-check -q -r ..\escritorio\requirements.txt -r ..\backend\requirements.txt || goto :error

echo [2/5] Copiando las llaves del backend a %LLAVES%...
if not exist "..\backend\.env" (
  echo Falta backend\.env con las llaves de Supabase y OpenRouter.
  goto :error
)
if not exist "%LOCALAPPDATA%\PortalTrabajador" mkdir "%LOCALAPPDATA%\PortalTrabajador"
copy /y "..\backend\.env" "%LLAVES%" >nul || goto :error

echo [3/5] Preparando icono y hoja de estilo...
pushd ..\escritorio
if not exist recursos\icono.ico python scripts\crear_icono.py || goto :error
python -m app.tema || goto :error
popd

echo [4/5] Creando el ejecutable con PyInstaller (tarda unos minutos)...
python -m PyInstaller portal_personal.spec --noconfirm --clean --workpath "%BUILD%\work" --distpath "%BUILD%\dist" || goto :error
start "" /wait "%DIST%\PortalTrabajador.exe" --verificar
if errorlevel 1 (
  echo La verificacion del ejecutable fallo. Revisa %LOCALAPPDATA%\PortalTrabajador\Logs\portal.log
  goto :error
)
echo Ejecutable verificado: %DIST%\PortalTrabajador.exe

echo [5/5] Creando el instalador con Inno Setup...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo No se encontro Inno Setup 6. El programa ya funciona desde: %DIST%\PortalTrabajador.exe
  goto :fin
)
"%ISCC%" /Q "/DDist=%DIST%" instalador_personal.iss || goto :error
echo Instalador listo en empaquetado\salida\PortalTrabajador-Personal-1.1.0.exe

:fin
endlocal
exit /b 0

:error
echo.
echo Hubo un error. Revisa los mensajes de arriba.
endlocal
exit /b 1
