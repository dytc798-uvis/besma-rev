# `.secrets/` (로컬 전용)

이 폴더는 Git에서 **내용 파일을 무시**합니다. 여기에만 두세요.

- `besma-key.pem` — SSH용 개인키 (저장소에 올리지 말 것)

권한(Windows): PowerShell에서 저장소 루트 기준 예시

```powershell
icacls ".\.secrets\besma-key.pem" /inheritance:r
icacls ".\.secrets\besma-key.pem" /grant:r "${env:USERNAME}:R"
```

SSH 예시:

```powershell
ssh -i ".\.secrets\besma-key.pem" ubuntu@api.besma.co.kr
```
