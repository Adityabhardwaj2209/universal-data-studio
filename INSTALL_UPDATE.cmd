@echo off
setlocal
set "STUDIO_TARGET=%USERPROFILE%\sales-report-automation"
if not "%~1"=="" set "STUDIO_TARGET=%~1"
if not exist "%STUDIO_TARGET%\.venv\Scripts\python.exe" (
  echo Project Python not found: %STUDIO_TARGET%\.venv\Scripts\python.exe
  echo Run INSTALL_UPDATE.cmd "C:\path\to\sales-report-automation"
  pause
  exit /b 1
)
"%STUDIO_TARGET%\.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 exit /b 1
"%STUDIO_TARGET%\.venv\Scripts\python.exe" "%~dp0install_upgrade.py" --target "%STUDIO_TARGET%"
if errorlevel 1 exit /b 1
cd /d "%STUDIO_TARGET%"
"%STUDIO_TARGET%\.venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
