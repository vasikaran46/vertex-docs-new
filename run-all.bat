@echo off
title Vertex Docs Launcher
echo Starting Backend...
start "Vertex Docs - Backend" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --reload-dir app --port 8000"
echo Starting Frontend...
start "Vertex Docs - Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
echo Both servers are launching!
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000
