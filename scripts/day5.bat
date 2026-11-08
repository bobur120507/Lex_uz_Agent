@echo off
rem Modda, 5-kun: demo oldidan yakuniy tekshiruv. Natija: data\reports\TAYYORLIK.md
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo .venv topilmadi - avval scripts\setup_server.bat ni ishga tushiring.
  pause
  exit /b 1
)
for /f "delims=" %%P in ('".venv\Scripts\python.exe" -c "import sys; print(sys.base_prefix)"') do set "BASEPY=%%P\python.exe"
if not exist "%BASEPY%" set "BASEPY=.venv\Scripts\python.exe"
"%BASEPY%" "%~dp0day5.py" %*
set "CODE=%ERRORLEVEL%"
echo.
pause
exit /b %CODE%
