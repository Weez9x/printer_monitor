@echo off
cd /d "%~dp0"
start "Монитор принтеров" /min py -3 "%~dp0desktop_app.py"
