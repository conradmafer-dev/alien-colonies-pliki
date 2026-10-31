@echo off
cd /d "%~dp0backend"
py -3 start_web.py --local-data .\local_data --port 8080
pause
