from enum import Enum


class Role(str, Enum):
    HQ_SAFE = "HQ_SAFE"
    SITE = "SITE"
    HQ_OTHER = "HQ_OTHER"
    WORKER = "WORKER"
    HQ_SAFE_ADMIN = "HQ_SAFE_ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"


class UIType(str, Enum):
    HQ_SAFE = "HQ_SAFE"
    SITE = "SITE"
    HQ_OTHER = "HQ_OTHER"

