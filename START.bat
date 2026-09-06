@echo off
title Upay QR Code
color 0E
cls
echo.
echo  ====================================================
echo     UPAY QR CODE AUTOMATION
echo  ====================================================
echo.

if exist "setup_done.txt" (
    echo  Setup already complete. Starting...
    goto START
)

echo  First time setup...
python --version >nul 2>&1
if errorlevel 1 (
    echo  Python not found! Install from Microsoft Store.
    pause
    exit
)

echo  Installing libraries...
python -m pip install --quiet requests pandas openpyxl pdfplumber qrcode reportlab
echo Setup completed on %DATE% > setup_done.txt
echo  Setup complete!

:START
echo.
echo  Generating portal data...
python demo_data.py

echo.
echo  Starting Portal API (port 8000)...
start "Portal API" python portal_api.py
timeout /t 2 /nobreak >nul

echo  Starting Portal (port 8001)...
start "Portal" python portal.py
timeout /t 2 /nobreak >nul

echo  Starting Automation Dashboard (port 5000)...
echo.
echo  ====================================================
echo   Portal URL    : http://localhost:8001
echo   Automation Dashboard: http://localhost:5000
echo   Login credentials  : sifaul / sifaul123
echo  ====================================================
echo.

start http://localhost:8001

python server.py
pause