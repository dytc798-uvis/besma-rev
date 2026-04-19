# -*- coding: utf-8 -*-
from __future__ import annotations

from pydantic import BaseModel, Field


class SafetyEducationDeleteRequest(BaseModel):
    password: str = Field(..., min_length=1, description="본인 계정 비밀번호 확인")
