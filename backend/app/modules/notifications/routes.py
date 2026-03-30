from fastapi import APIRouter


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications():
    # TODO: 실제 알림 데이터 연동 (현재는 placeholder)
    return []

