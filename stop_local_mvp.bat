@echo off
setlocal
title BESMA Local MVP Stopper

echo [BESMA] Stopping launcher windows...
taskkill /FI "WINDOWTITLE eq BESMA Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq BESMA Frontend*" /T /F >nul 2>&1

for %%P in (8001 5174) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do (
    taskkill /PID %%A /T /F >nul 2>&1
  )
)

echo [BESMA] Stop command sent.
