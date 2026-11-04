@echo off
cd /d %~dp0
where adb >nul 2>nul || echo [WARN] adb not in PATH - install Android platform-tools or set ADB_PATH
python main.py
pause
