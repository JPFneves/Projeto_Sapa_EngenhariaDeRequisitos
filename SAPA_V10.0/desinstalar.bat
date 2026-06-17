@echo off
:: ============================================================
::  SAPA v9.0 — desinstalar.bat
::  Remove o SAPA instalado via instalar.bat / Inno Setup.
::  Execute como Administrador se o SAPA foi instalado para
::  todos os usuários (Program Files).
:: ============================================================

title SAPA — Desinstalador

echo.
echo  ================================================
echo   SAPA v9.0  ^|  Desinstalador
echo  ================================================
echo.

:: ── Caminho padrão de instalação ─────────────────────────────────────────────
set "SAPA_DIR=%ProgramFiles%\SAPA"
if not exist "%SAPA_DIR%" set "SAPA_DIR=%LocalAppData%\Programs\SAPA"
if not exist "%SAPA_DIR%" set "SAPA_DIR=%~dp0"

:: ── Verifica se o SAPA está em execução ──────────────────────────────────────
tasklist /fi "IMAGENAME eq SAPA.exe" 2>nul | find /i "SAPA.exe" >nul
if not errorlevel 1 (
    echo [AVISO] O SAPA esta em execucao. Encerrando...
    taskkill /f /im SAPA.exe >nul 2>&1
    timeout /t 2 /nobreak >nul
)

:: ── Confirmação ──────────────────────────────────────────────────────────────
echo  Pasta de instalacao detectada:
echo  %SAPA_DIR%
echo.
set /p CONFIRMA= Deseja remover o SAPA? (S/N): 
if /i not "%CONFIRMA%"=="S" (
    echo Operacao cancelada.
    pause & exit /b 0
)

:: ── Pergunta sobre o banco de dados ──────────────────────────────────────────
echo.
set /p MANTER_BANCO= Manter o banco de dados (historico de presencas)? (S/N): 

:: ── Remove atalhos ───────────────────────────────────────────────────────────
echo.
echo [1/4] Removendo atalhos...
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\SAPA" (
    rmdir /s /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\SAPA" 2>nul
)
if exist "%PUBLIC%\Desktop\SAPA.lnk"          del /q "%PUBLIC%\Desktop\SAPA.lnk"
if exist "%USERPROFILE%\Desktop\SAPA.lnk"     del /q "%USERPROFILE%\Desktop\SAPA.lnk"
echo       OK

:: ── Remove entrada de inicialização automática ───────────────────────────────
echo [2/4] Removendo inicializacao automatica...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "SAPA" /f >nul 2>&1
echo       OK

:: ── Remove arquivos (preserva banco se pedido) ───────────────────────────────
echo [3/4] Removendo arquivos...
if /i "%MANTER_BANCO%"=="S" (
    if exist "%SAPA_DIR%\banco_sapa.db" (
        copy /y "%SAPA_DIR%\banco_sapa.db" "%USERPROFILE%\Desktop\banco_sapa_backup.db" >nul
        echo       Banco de dados copiado para: %USERPROFILE%\Desktop\banco_sapa_backup.db
    )
)

if exist "%SAPA_DIR%" (
    rmdir /s /q "%SAPA_DIR%"
    echo       Pasta removida: %SAPA_DIR%
) else (
    echo       Pasta nao encontrada — nada a remover.
)
echo       OK

:: ── Remove entrada do Painel de Controle (se instalado via Inno Setup) ───────
echo [4/4] Removendo registro do Windows...
for /f "tokens=*" %%k in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "SAPA" /k 2^>nul') do (
    reg delete "%%k" /f >nul 2>&1
)
for /f "tokens=*" %%k in ('reg query "HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "SAPA" /k 2^>nul') do (
    reg delete "%%k" /f >nul 2>&1
)
for /f "tokens=*" %%k in ('reg query "HKLM\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall" /s /f "SAPA" /k 2^>nul') do (
    reg delete "%%k" /f >nul 2>&1
)
echo       OK

echo.
echo  ================================================
echo   SAPA removido com sucesso!
if /i "%MANTER_BANCO%"=="S" (
echo   Backup do banco salvo na Area de Trabalho:
echo   banco_sapa_backup.db
)
echo  ================================================
echo.
pause
