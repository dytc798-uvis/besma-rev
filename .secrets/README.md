# `.secrets/` (로컬 전용)

이 폴더는 Git에서 **내용 파일을 무시**합니다. 여기에만 두세요.

- `besma-key.pem` — SSH용 개인키 (저장소에 올리지 말 것)

## 권한이 안 맞을 때 (Windows)

OpenSSH는 **“나 말고 다른 주체가 읽을 수 있으면”** 키를 거부합니다.  
`icacls` 가 **권한 없음**으로 실패하면, 대부분 **파일 소유자가 아니거나 상위 폴더 ACL** 때문입니다.

### 방법 A — 자동 스크립트 (먼저 시도)

저장소 루트에서:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\fix_ssh_key_permissions.ps1
```

루트에만 키가 있으면 그 경로를 잡고, `.secrets\besma-key.pem` 이 있으면 그쪽을 우선합니다.

**여전히 거절되면** (같은 스크립트, 홈 `.ssh`로 복사 후 그 파일만 ACL 조정 — 여기가 잘 됨):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\fix_ssh_key_permissions.ps1 -CopyToUserSsh
```

이후 SSH는 출력에 나온 `C:\Users\...\ .ssh\besma-key.pem` 경로를 `-i` 로 사용하면 됩니다.

### 방법 B — 관리자 권한 + 소유권 (A가 안 될 때)

1. **PowerShell을 관리자 권한으로 실행**
2. (키 경로에 맞게 수정)

```cmd
takeown /f "D:\besma-rev\.secrets\besma-key.pem"
icacls "D:\besma-rev\.secrets\besma-key.pem" /inheritance:r
icacls "D:\besma-rev\.secrets\besma-key.pem" /grant:r "%USERNAME%:R"
```

### SSH 예시

```powershell
ssh -i "D:\besma-rev\.secrets\besma-key.pem" ubuntu@api.besma.co.kr
```

( `-CopyToUserSsh` 를 썼다면 스크립트가 안내한 `%USERPROFILE%\.ssh\besma-key.pem` 경로 사용)
