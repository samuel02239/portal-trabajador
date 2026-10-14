; Instalador de Windows (Inno Setup 6) para el Portal del Trabajador.
; Lo compila construir.bat. A mano:  ISCC.exe "/DDist=C:\ruta\dist\PortalTrabajador" instalador.iss
; Requiere haber corrido antes PyInstaller.

#ifndef Dist
  #define Dist "dist\PortalTrabajador"
#endif
#define Nombre "Portal del Trabajador"
#define Version "1.1.0"
#define Editor "Portal del Trabajador"
#define Exe "PortalTrabajador.exe"

[Setup]
AppId={{6C2B3F7E-6E1D-4C55-9C0A-5B1F7A2E9D41}
AppName={#Nombre}
AppVersion={#Version}
AppPublisher={#Editor}
; Se instala para el usuario actual: no pide permisos de administrador
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\PortalTrabajador
DefaultGroupName={#Nombre}
DisableProgramGroupPage=yes
OutputDir=salida
OutputBaseFilename=PortalTrabajador-Instalador-{#Version}
SetupIconFile=..\escritorio\recursos\icono.ico
UninstallDisplayIcon={app}\{#Exe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; Cierra el programa si está abierto antes de actualizarlo
CloseApplications=yes
; Firma digital (recomendado para evitar la alerta de SmartScreen). Configura la herramienta "firmar"
; en Inno Setup (Tools > Configure Sign Tools) con tu certificado de firma de código y descomenta:
; SignTool=firmar
; SignedUninstaller=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[InstallDelete]
; Quita los archivos de la versión anterior (incluido el backend de la versión personal) antes de copiar los nuevos
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#Dist}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#Nombre}"; Filename: "{app}\{#Exe}"
Name: "{group}\Desinstalar {#Nombre}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#Nombre}"; Filename: "{app}\{#Exe}"; Tasks: escritorio

[Run]
Filename: "{app}\{#Exe}"; Description: "Abrir {#Nombre}"; Flags: nowait postinstall skipifsilent
