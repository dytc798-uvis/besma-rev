# 기능인제 평가자 계정표 (소장·팀장)

> 이전에 `sites.project_manager`(공무)로 채워진 파일은 **폐기**했습니다.  
데이터: 월별현장별집계 + 출역일보 + **`docs/sample/site_import/raw` 일용직 사원리스트**(소장·주민번호 우선)

생성 명령:

```bash
cd backend
PYTHONPATH=. python scripts/generate_functional_eval_evaluator_account_sheets.py ../docs/new-site-deployment/현장소장계정
```

상세 규칙: [기능인제_평가자계정/README.md](../../기능인제_평가자계정/README.md)

신규현장 배포(비번 `1111`) 전용 표는 `scripts/generate_new_site_deployment_manager_account_sheets.py` 입니다.
