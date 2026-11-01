"""Unapplied migration candidate: manual ERP intake policy is OFF by default."""
import os
from fastapi import HTTPException
FLAG = "BESMA_FE_DESKTOP_INTAKE_REQUIRED"

def read_manual_erp_intake_policy():
    raw = os.getenv(FLAG, "false").strip().lower()
    return {"false": "MANUAL_ALLOWED", "true": "WORKBENCH_REQUIRED"}.get(raw, "CHECK_REQUIRED")

def assert_manual_erp_import_allowed():
    policy = read_manual_erp_intake_policy()
    if policy == "CHECK_REQUIRED":
        raise HTTPException(status_code=503, detail={"code": "INTAKE_POLICY_INVALID", "message": "자료 수신 설정을 확인하세요."})
    if policy == "WORKBENCH_REQUIRED":
        raise HTTPException(status_code=409, detail={"code": "DESKTOP_VALIDATED_INTAKE_REQUIRED", "message": "ERP 자료는 Safety Workbench의 평가자료 수신에서 등록하세요."})
