@echo off
setlocal
title BESMA Backend

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%backend"

set "ENV=local"
set "DEV_BYPASS_AUTH=true"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] backend venv python not found: .venv\Scripts\python.exe
  echo [HINT] run: cd backend ^&^& py -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

echo [BESMA] Running alembic migrations...
".venv\Scripts\python.exe" -m alembic upgrade head
if errorlevel 1 (
  echo [ERROR] alembic upgrade head failed.
  pause
  exit /b 1
)

echo [BESMA] Running seed data sync...
".venv\Scripts\python.exe" -m app.seed.seed_data
if errorlevel 1 (
  echo [ERROR] seed_data sync failed.
  pause
  exit /b 1
)

echo [BESMA] Backend starting on http://0.0.0.0:8001
echo [BESMA] External test URL: http://118.36.137.127:8001
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
