@echo off
cd /d %~dp0..
cd backend
REM Python 3.12+ 권장 (3.14 환경에서는 pydantic-core 빌드 이슈 가능)
py -3.12 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

