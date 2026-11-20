@echo off
REM Startet das QT-Tool im Browser. Fenster offen lassen, solange das Tool benutzt wird.
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python -m streamlit run app.py
pause
