@echo off
title CHINTU Robot Control Platform
echo ========================================================
echo   Starting CHINTU Robot Control Platform
echo   Localhost: http://localhost:8973
echo ========================================================
echo.
echo Installing dependencies if needed...
pip install -r requirements.txt --quiet
echo.
echo Opening browser...
start http://localhost:8973
echo.
echo Starting Python Server...
python server.py
pause
