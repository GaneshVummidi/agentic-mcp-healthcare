#!/usr/bin/env bash
# MediAegis AI - one-shot local startup (macOS / Linux)
set -e

cd "$(dirname "$0")/backend"

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt --quiet

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created backend/.env from .env.example - edit it to add optional API keys."
fi

echo "Starting MediAegis AI on http://localhost:8000 ..."
python main.py
