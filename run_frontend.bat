@echo off
setlocal
title BESMA Frontend

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%frontend"

if not exist "package.json" (
  echo [ERROR] frontend\package.json not found.
  pause
  exit /b 1
)

if not exist "node_modules" (
  echo [BESMA] node_modules not found. running npm install...
  npm install
  if errorlevel 1 (
    echo [ERROR] npm install failed.
    pause
    exit /b 1
  )
)

echo [BESMA] Frontend starting on http://0.0.0.0:5174
echo [BESMA] External test URL: http://118.36.137.127:5174
npm run dev -- --host 0.0.0.0 --port 5174 --strictPort
