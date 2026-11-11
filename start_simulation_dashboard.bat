@echo off
title Chintu Robot Simulation Dashboard
echo ========================================================
echo   Starting Chintu Biped Robot Simulation Server...
echo ========================================================
echo.

:: Launch mock server via WSL
start /B wsl python3 /mnt/c/Users/Robodroide/Desktop/chintu/chintutherobo/robot/tools/mock_ws_server.py

timeout /t 2 >nul

:: Open dashboard in default browser
echo Opening Dashboard at http://localhost:3456 ...
start http://localhost:3456

echo.
echo ========================================================
echo   Dashboard is running! Keep this window open.
echo   Press Ctrl+C to stop.
echo ========================================================
pause

