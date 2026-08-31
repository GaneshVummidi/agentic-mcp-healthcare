@echo off
cd /d "%~dp0backend"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet

if not exist .env (
    copy .env.example .env
    echo Created backend\.env from .env.example - edit it to add optional API keys.
)

echo Starting MediAegis AI on http://localhost:8000 ...
python main.py
