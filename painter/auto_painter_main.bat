@echo off
cd /d "%~dp0"

echo Installing dependencies...
pip install -r requirements.txt >nul 2>&1

echo Starting Auto Painter...
python auto_painter.py

echo Finished. Press any key to exit.
pause
