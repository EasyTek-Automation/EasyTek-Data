@echo off
:: SAP Job Scheduler - dispara job manualmente (Bloco I A-04 fallback).
::
:: Versao clicavel: pergunta o tipo e dispara via PowerShell.
:: Para versao terminal, use disparar_job.ps1 <tipo>.

setlocal

echo.
echo  ==================================================
echo   SAP Job Scheduler - Disparo Manual de Job
echo  ==================================================
echo.
echo  Tipos disponiveis:
echo    1) zppprd       (apontamentos / producao)
echo    2) zpp_nt0001   (paradas / breakdowns)
echo.

set /p escolha="Tipo (1 ou 2): "

if "%escolha%"=="1" (
    set "tipo=zppprd"
) else if "%escolha%"=="2" (
    set "tipo=zpp_nt0001"
) else (
    echo.
    echo  ERRO: opcao invalida.
    pause
    exit /b 1
)

echo.
echo  Disparando: %tipo%
echo.

powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0disparar_job.ps1" -tipo %tipo%

if %ERRORLEVEL% neq 0 (
    echo.
    echo  ERRO: falha no disparo. Veja mensagem acima.
)

echo.
pause
endlocal
