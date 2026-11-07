@echo off
rem Modda: double-click to set everything up on Windows (installs Python 3.12 first if it is missing).
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
set "PY="
where py >nul 2>&1 && py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1 && set "PY=py -3"
if not defined PY (
  where python >nul 2>&1 && python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1 && set "PY=python"
)
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY (
  echo Python topilmadi - Python 3.12 o'rnatilmoqda ^(winget^)...
  winget install --id Python.Python.3.12 -e --scope user --silent --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PY (
  echo.
  echo Python o'rnatilmadi. https://www.python.org/downloads/ dan Python 3.12 ni o'rnating
  echo ^("Add python.exe to PATH" belgisini qo'ying^), keyin shu faylni qayta ishga tushiring.
  pause
  exit /b 1
)
echo Python: %PY%
%PY% "%~dp0setup_windows.py" %*
set "CODE=%ERRORLEVEL%"
echo.
pause
exit /b %CODE%
