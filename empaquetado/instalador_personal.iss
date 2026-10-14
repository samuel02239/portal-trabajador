; Instalador PERSONAL (pruebas, un solo PC) del Portal del Trabajador: el backend va dentro del programa.
; Lo compila construir_personal.bat. Las llaves no van aquí: quedan en %LOCALAPPDATA%\PortalTrabajador\backend.env.

#ifndef Dist
  #define Dist "dist\PortalTrabajador"
#endif
#define Nombre "Portal del Trabajador"
#define Version "1.1.0"
#define Editor "Portal del Trabajador"
#define Exe "PortalTrabajador.exe"

[Setup]
; Mismo AppId que el instalador anterior: si ya estaba instalado, se actualiza en el mismo lugar
AppId={{6C2B3F7E-6E1D-4C55-9C0A-5B1F7A2E9D41}
AppName={#Nombre}
AppVersion={#Version}
AppPublisher={#Editor}
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\PortalTrabajador
DefaultGroupName={#Nombre}
DisableProgramGroupPage=yes
OutputDir=salida
OutputBaseFilename=PortalTrabajador-Personal-{#Version}
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

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[InstallDelete]
; Quita los archivos de la versión anterior para que no se mezclen con los nuevos
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#Dist}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#Nombre}"; Filename: "{app}\{#Exe}"
Name: "{group}\Desinstalar {#Nombre}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#Nombre}"; Filename: "{app}\{#Exe}"; Tasks: escritorio

[Run]
Filename: "{app}\{#Exe}"; Description: "Abrir {#Nombre}"; Flags: nowait postinstall skipifsilent
