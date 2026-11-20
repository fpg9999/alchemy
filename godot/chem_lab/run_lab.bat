@echo off
setlocal
cd /d "%~dp0"
set HERE=%CD%

set GODOT=G:\Godot_v4.7.2-stable_win64.exe\Godot_v4.7.2-stable_win64.exe
set PY=python

if not exist "%GODOT%" (
  echo [ERROR] Godot not found: %GODOT%
  echo Edit the GODOT variable in run_lab.bat, or put Godot there.
  pause
  exit /b 1
)

echo [1/2] start Python kernel server on 127.0.0.1:8765 ...
start "chem_kernel" /min %PY% "%HERE%\kernel_server.py"
ping -n 4 127.0.0.1 >nul

echo [2/2] start Godot ChemLab ...
start "" "%GODOT%" --path "%HERE%"

echo done. The kernel runs in the minimized 'chem_kernel' console.
echo Press any key to close this launcher window.
pause >nul
exit /b 0
