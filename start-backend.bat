@echo off
title Vertex Docs - Backend
cd /d "%~dp0backend"
call .venv\Scripts\activate.bat
uvicorn app.main:app --reload --reload-dir app --port 8000
pause
