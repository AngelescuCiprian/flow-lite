@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call install.bat

rem ---- Settings (edit here, or set them as Windows environment variables) ----
if not defined FLOW_LANGS set "FLOW_LANGS=ro,en"
if not defined FLOW_MODEL set "FLOW_MODEL=large-v3-turbo"
if not defined FLOW_KEY set "FLOW_KEY=ctrl_r"
if not defined FLOW_INSERT set "FLOW_INSERT=paste"
rem if not defined FLOW_WORDS set "FLOW_WORDS=Ciprian,GitHub"
rem ---------------------------------------------------------------------------

title Flow-lite
.venv\Scripts\python flow_lite.py
pause
