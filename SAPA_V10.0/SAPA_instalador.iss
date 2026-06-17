; ============================================================
;  SAPA v9.0 — Instalador Windows
;  Gerado com Inno Setup 6 — https://jrsoftware.org/isinfo.php
;
;  COMO USAR:
;  1. Baixe e instale o Inno Setup 6 (gratuito)
;  2. Coloque este arquivo .iss na mesma pasta que o SAPA
;  3. Clique com botão direito → "Compile"
;  4. O instalador .exe aparece na pasta Output\
; ============================================================

#define MyAppName      "SAPA"
#define MyAppVersion   "9.0"
#define MyAppPublisher "UNISEPE — ADS"
#define MyAppExeName   "SAPA.exe"
#define MyAppURL       "https://github.com/sapa-unisepe"

[Setup]
; Identificador único — NÃO MUDE depois de distribuir
AppId={{B4F2C1A0-3D7E-4F2B-9C1A-5E8D2B3F4A6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\SAPA
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Ícone do instalador e do painel Adicionar/Remover Programas
SetupIconFile=sapa.ico
UninstallDisplayIcon={app}\sapa.ico
; Pasta de saída do .exe gerado
OutputDir=Output
OutputBaseFilename=SAPA_v9_Instalador
; Compressão máxima
Compression=lzma2/ultra64
SolidCompression=yes
; Requer Windows 10 64-bit ou superior
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64
; Pede elevação de administrador apenas se necessário
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Marca o desinstalador
UninstallDisplayName={#MyAppName} v{#MyAppVersion}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon";    Description: "Criar ícone na Área de Trabalho";      GroupDescription: "Atalhos:"; Flags: checkedonce
Name: "startupicon";    Description: "Iniciar com o Windows automaticamente"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
; Executável principal (gerado pelo PyInstaller — veja instalar.bat)
Source: "dist\SAPA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Ícone separado na raiz do app (para o atalho e desinstalador)
Source: "sapa.ico";    DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Menu Iniciar
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\sapa.ico"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"

; Área de Trabalho (opcional — marcado por padrão na task acima)
Name: "{autodesktop}\{#MyAppName}";     Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\sapa.ico"; Tasks: desktopicon

[Registry]
; Inicialização automática com o Windows (opcional)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SAPA"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
; Abre o SAPA ao final da instalação (opcional)
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir o SAPA agora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove o banco local ao desinstalar (opcional — descomente se quiser)
; Type: files; Name: "{app}\banco_sapa.db"
; Remove a pasta inteira se estiver vazia
Type: dirifempty; Name: "{app}"

[Code]
// ── Verifica se o Python/PyInstaller já está no PATH ──────────────────────
// (Opcional: útil se quiser rodar a partir do fonte em vez do dist/)
// Descomente abaixo se quiser verificar pré-requisitos no instalador.

// procedure CurStepChanged(CurStep: TSetupStep);
// begin
//   if CurStep = ssInstall then begin
//     if not FileExists(ExpandConstant('{app}\SAPA.exe')) then begin
//       MsgBox('SAPA.exe não encontrado em dist\SAPA\. Execute instalar.bat primeiro.', mbError, MB_OK);
//       Abort;
//     end;
//   end;
// end;
