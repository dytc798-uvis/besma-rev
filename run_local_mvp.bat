@echo off
setlocal
title BESMA Local MVP Launcher

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

if not exist "run_backend.bat" (
  echo [ERROR] run_backend.bat not found.
  pause
  exit /b 1
)

if not exist "run_frontend.bat" (
  echo [ERROR] run_frontend.bat not found.
  pause
  exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] backend venv python not found: backend\.venv\Scripts\python.exe
  echo [HINT] run: cd backend ^&^& py -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

echo [BESMA] Preflight OK.
echo [BESMA] Backend startup will run:
echo   1) alembic upgrade head
echo   2) seed_data sync
echo.

echo [BESMA] Launching backend and frontend in separate windows...
start "BESMA Backend" cmd /k call "%ROOT_DIR%run_backend.bat"
start "BESMA Frontend" cmd /k call "%ROOT_DIR%run_frontend.bat"

echo [BESMA] Started.
echo - Backend:  http://127.0.0.1:8001/health
echo - Frontend: http://127.0.0.1:5174
echo - Swagger:  http://127.0.0.1:8001/docs
echo - External Frontend: http://118.36.137.127:5174
echo - External Backend:  http://118.36.137.127:8001/health
