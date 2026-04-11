@echo off
title ManualFinder RAG Indexer

set ROOT=%~dp0
if "%ROOT:~-1%"=="\" set ROOT=%ROOT:~0,-1%

set BACKEND=%ROOT%\backend
set PYDIR=%ROOT%\.python311
set PYTHON=%PYDIR%\python.exe
set PIP=%PYDIR%\Scripts\pip.exe
set REQ=%BACKEND%\requirements-local.txt
set STAMP=%PYDIR%\req_stamp.txt

set PY_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip
set PY_ZIP=%ROOT%\.python311.zip
set GETPIP_URL=https://bootstrap.pypa.io/get-pip.py
set GETPIP=%PYDIR%\get-pip.py

echo.
echo ================================================
echo   ManualFinder - Indicizzatore RAG locale
echo ================================================
echo.

if not exist "%BACKEND%" (
    echo ERRORE: cartella backend non trovata: %BACKEND%
    goto :fine
)

if exist "%PYTHON%" goto :python_ok

echo Download Python 3.11 standalone...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_ZIP%'"
if errorlevel 1 (
    echo ERRORE: download Python fallito.
    goto :fine
)

echo Estrazione...
if not exist "%PYDIR%" mkdir "%PYDIR%"
powershell -Command "Expand-Archive -Path '%PY_ZIP%' -DestinationPath '%PYDIR%' -Force"
del "%PY_ZIP%"

echo Configurazione Python...
powershell -Command "(Get-Content '%PYDIR%\python311._pth') -replace '#import site','import site' | Set-Content '%PYDIR%\python311._pth'"

echo Download pip...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%GETPIP_URL%' -OutFile '%GETPIP%'"
"%PYTHON%" "%GETPIP%" --quiet
del "%GETPIP%"
echo Python 3.11 pronto.
echo.

:python_ok
echo [OK] Python standalone trovato

if exist "%STAMP%" goto :deps_ok

echo Installazione dipendenze (prima volta: 2-5 minuti)...
"%PIP%" install -r "%REQ%"
if errorlevel 1 (
    echo ERRORE: installazione dipendenze fallita.
    goto :fine
)
echo installato > "%STAMP%"
echo [OK] Dipendenze installate
goto :avvia

:deps_ok
echo [OK] Dipendenze presenti

:: Verifica compatibilita' NumPy — chromadb 0.5.x non gira con NumPy 2.x
"%PYTHON%" -c "import numpy as np; v=tuple(int(x) for x in np.__version__.split('.')[:2]); exit(0 if v<(2,0) else 1)" 2>nul
if errorlevel 1 (
    echo [FIX] NumPy 2.x incompatibile con chromadb. Downgrade a 1.x in corso...
    "%PIP%" install "numpy>=1.26.0,<2.0" --quiet
)

:avvia
echo.
echo Apertura http://localhost:7777 ...
echo (Ctrl+C per fermare)
echo.
cd /d "%BACKEND%"
set ANONYMIZED_TELEMETRY=False
set CHROMA_TELEMETRY=False
"%PYTHON%" -c "import sys; sys.path.insert(0, r'%BACKEND%'); from app.local_indexer.__main__ import main; main()"

:fine
echo.
pause
