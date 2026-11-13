@echo off
cd /d "%~dp0"
python -m streamlit run household_app/app.py --server.port 8502
if errorlevel 1 pause
