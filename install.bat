@echo off
setlocal
cd /d "%~dp0"

rem Prefer Python 3.13 (widest wheel support), then any Python 3 from the py launcher, then python.
set "PY="
py -3.13 --version >nul 2>nul && set "PY=py -3.13"
if not defined PY py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY set "PY=python"

echo Creating virtual environment with %PY% ...
%PY% -m venv .venv || goto :fail
.venv\Scripts\python -m pip install --upgrade pip || goto :fail
.venv\Scripts\python -m pip install -r requirements.txt || goto :fail

where nvidia-smi >nul 2>nul
if not errorlevel 1 (
    echo NVIDIA GPU found, installing CUDA libraries into .venv ...
    .venv\Scripts\python -m pip install -r requirements-gpu.txt || goto :fail
)

echo.
echo Testing model, microphone and clipboard. The first run downloads the model (about 1.6 GB).
.venv\Scripts\python flow_lite.py --check || goto :fail
echo.
echo Done. Double-click start.bat to dictate.
pause
exit /b 0

:fail
echo.
echo Installation failed - see the messages above.
pause
exit /b 1
