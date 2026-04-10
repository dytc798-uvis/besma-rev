# BESMA 백엔드 systemd 운영·배포

대상 경로(운영 서버 기준):

| 항목 | 경로 |
|------|------|
| 프로젝트 루트 | `/home/ubuntu/besma-rev` |
| 백엔드 | `/home/ubuntu/besma-rev/backend` |
| venv | `/home/ubuntu/besma-rev/backend/.venv` |
| systemd 유닛 파일(저장소) | `deploy/systemd/besma-backend.service` |
| 배포 스크립트 | `deploy/deploy_backend.sh` |

확인된 운영 접속값(2026-04-10):

| 항목 | 값 |
|------|------|
| SSH Host | `api.besma.co.kr` |
| SSH User | `ubuntu` |
| SSH Key (로컬) | `C:\Users\win10\Downloads\besma-key.pem` |
| 서비스 유닛 | `besma-backend.service` |
| 헬스체크 | `http://127.0.0.1:8001/health` |

nginx·Vercel 프론트는 이 문서 범위 밖입니다.

---

## .env / DB 경로 점검 포인트

- `backend/app/config/settings.py`의 `BASE_DIR`은 **저장소 루트**(`besma-rev`)입니다.
- `.env`는 기본적으로 **`/home/ubuntu/besma-rev/.env`** 를 읽습니다. `WorkingDirectory`가 `backend`여도 앱은 이 경로를 사용합니다.
- SQLite를 쓰는 경우 DB 파일은 보통 **`/home/ubuntu/besma-rev/database/besma.db`** (코드 기본값 기준)입니다. 운영에서 다른 DB를 쓰면 `.env`와 실제 DB 위치가 일치하는지 확인하세요.
- systemd의 `User=ubuntu`이므로 **해당 사용자가 DB·스토리지 디렉터리에 읽기/쓰기 가능**해야 합니다 (`storage/` 등).

---

## Health check 권장 방식

| 방식 | 용도 |
|------|------|
| **`curl http://127.0.0.1:8001/health`** | **권장.** systemd로 띄운 uvicorn 프로세스가 직접 응답하는지 확인. nginx/SSL과 무관. |
| `curl https://api.besma.co.kr/health` | 엣지(nginx, 인증서, 프록시)까지 포함한 통합 확인용. 배포 스크립트 기본값으로는 부적합할 수 있음(일시 네트워크/인증서 이슈와 구분 어려움). |
| `GET /docs` | 가능하나 HTML이라 파싱이 불편. 앱에 이미 **`GET /health`** 가 있으므로 후자를 사용. |

배포 스크립트 기본: `http://127.0.0.1:8001/health`  
환경 변수로 변경: `BESMA_HEALTH_URL=... ./deploy/deploy_backend.sh`

---

## nohup uvicorn → systemd 전환 절차

**충돌 방지:** 기존 수동 프로세스가 같은 `127.0.0.1:8001` 에 바인딩 중이면 `systemctl start`가 실패하거나 포트가 점유됩니다.

1. **기존 프로세스 확인**
   ```bash
   ss -ltnp | grep 8001
   # 또는
   pgrep -af uvicorn
   ```
2. **수동 uvicorn 종료** (해당 PID로 교체)
   ```bash
   kill <PID>
   # 응답 없으면: kill -9 <PID>
   ```
3. **유닛 설치·기동** (아래 [최초 적용 순서](#최초-적용-순서) 참고)
4. **검증**
   ```bash
   curl -fsS http://127.0.0.1:8001/health
   sudo systemctl status besma-backend --no-pager
   ```

---

## 최초 적용 순서

1. 저장소에서 유닛 파일 복사 (**sudo**)
   ```bash
   sudo cp /home/ubuntu/besma-rev/deploy/systemd/besma-backend.service /etc/systemd/system/besma-backend.service
   ```
2. 필요 시 `/etc/systemd/system/besma-backend.service` 에서 `User`/`Group`/`경로`를 서버에 맞게 수정.
3. 데몬 리로드·등록·기동 (**sudo**)
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable besma-backend
   sudo systemctl start besma-backend
   ```
4. 배포 스크립트 실행 권한 (한 번)
   ```bash
   chmod +x /home/ubuntu/besma-rev/deploy/deploy_backend.sh
   ```

---

## 운영 명령 (sudo가 필요한 항목 표시)

| 작업 | 명령 |
|------|------|
| 데몬 설정 다시 읽기 | `sudo systemctl daemon-reload` |
| 부팅 시 자동 시작 등록 | `sudo systemctl enable besma-backend` |
| 시작 | `sudo systemctl start besma-backend` |
| 중지 | `sudo systemctl stop besma-backend` |
| 재시작 | `sudo systemctl restart besma-backend` |
| 상태 | `systemctl status besma-backend` (보통 일반 사용자도 가능) |
| 최근 로그(팔로우) | `journalctl -u besma-backend -f` |
| 최근 로그 N줄 | `journalctl -u besma-backend -n 200 --no-pager` |
| 배포 실행 | `/home/ubuntu/besma-rev/deploy/deploy_backend.sh` |

---

## 검증 명령

```bash
# 서비스 상태
systemctl status besma-backend --no-pager

# 로컬 헬스 (권장)
curl -fsS http://127.0.0.1:8001/health

# (선택) 공개 도메인 경유
curl -fsS https://api.besma.co.kr/health
```

---

## 반자동 배포

```bash
cd /home/ubuntu/besma-rev
./deploy/deploy_backend.sh
```

Alembic을 같이 돌릴 때만:

```bash
RUN_MIGRATIONS=1 ./deploy/deploy_backend.sh
```

---

## 로컬(Windows) 원클릭 배포

저장소 루트에서 아래 PowerShell 스크립트를 실행하면
`frontend build -> git push -> 서버 backend 배포`를 순차 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\deploy_all.ps1
```

옵션 예시:

```powershell
# 프론트 빌드 생략
powershell -ExecutionPolicy Bypass -File .\deploy\deploy_all.ps1 -SkipFrontendBuild

# DB migration 생략
powershell -ExecutionPolicy Bypass -File .\deploy\deploy_all.ps1 -RunMigrations:$false

# push 없이 서버 배포만
powershell -ExecutionPolicy Bypass -File .\deploy\deploy_all.ps1 -SkipPush
```

---

## 실패 시 복구 (최소 절차)

1. **서비스 로그 확인**
   ```bash
   journalctl -u besma-backend -n 150 --no-pager
   ```
2. **설정/코드 되돌리기**
   ```bash
   cd /home/ubuntu/besma-rev
   git checkout <이전_커밋_또는_브랜치>
   ```
3. **venv·의존성 문제 시** (필요할 때만)
   ```bash
   cd /home/ubuntu/besma-rev/backend
   source .venv/bin/activate
   pip install -r requirements.txt   # 프로젝트 관례에 맞는 파일명 사용
   ```
4. **재기동**
   ```bash
   sudo systemctl restart besma-backend
   curl -fsS http://127.0.0.1:8001/health
   ```

포트 점유로 기동 실패 시: `ss -ltnp | grep 8001` 로 다른 프로세스를 종료한 뒤 다시 `restart`.

---

## systemd에서 `Restart=always` 로 바꾸고 싶을 때

현재 유닛은 **`Restart=on-failure`** (연속 크래시 루프 완화). 무중단에 가깝게 자동 재기동을 원하면 유닛 파일에서 `Restart=always` 로 바꾼 뒤 `daemon-reload` 및 `restart` 하세요.
