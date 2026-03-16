@echo off
cd /d "%~dp0"
if not exist .env (
    copy .env.example .env
    echo Created .env from .env.example — please fill in your credentials.
)
uvicorn app.main:app --reload --port 8001
