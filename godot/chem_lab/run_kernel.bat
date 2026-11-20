@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  ChemLab kernel server (Python sidecar)
echo  listening on 127.0.0.1:8765
echo  keep this window open; close it to stop
echo ============================================
python kernel_server.py
echo.
echo [kernel exited] press any key to close...
pause >nul
