@echo off
cd /d "%~dp0"

echo Installing dependencies...
pip install -r requirements.txt >nul 2>&1

echo Requesting Administrator Privilege...
powershell -Command "Start-Process python -ArgumentList 'auto_painter.py' -Verb RunAs -Wait"

echo Finished. Press any key to exit.
pause
