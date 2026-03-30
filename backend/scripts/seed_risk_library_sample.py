from __future__ import annotations

from datetime import date, datetime

from app.core.database import SessionLocal
from app.core.datetime_utils import utc_now
from app.modules.risk_library.models import (
    RiskLibraryItem,
    RiskLibraryItemRevision,
    RiskLibraryKeyword,
)


SAMPLES = [
    {
        "work_category": "철근/거푸집",
        "trade_type": "트레이 작업",
        "risk_factor": "사다리 작업 중 추락",
        "risk_cause": "불안정한 발판, 2인1조 미준수",
        "countermeasure": "2인1조 작업, 발판 고정, 추락방지구 설치",
        "risk_f": 3,
        "risk_s": 4,
        "risk_r": 12,
        "keywords": ["트레이", "사다리", "추락"],
    },
    {
        "work_category": "전기",
        "trade_type": "임시배선",
        "risk_factor": "누전/감전",
        "risk_cause": "피복 손상 케이블 사용",
        "countermeasure": "손상 케이블 교체, 누전차단기 점검",
        "risk_f": 2,
        "risk_s": 4,
        "risk_r": 8,
        "keywords": ["배선", "감전", "누전"],
    },
    {
        "work_category": "양중",
        "trade_type": "자재 인양",
        "risk_factor": "인양물 낙하",
        "risk_cause": "결속 불량",
        "countermeasure": "인양 전 결속점 재확인, 출입통제",
        "risk_f": 2,
        "risk_s": 5,
        "risk_r": 10,
        "keywords": ["양중", "인양", "낙하"],
    },
    {
        "work_category": "용접",
        "trade_type": "절단/용접",
        "risk_factor": "화재 발생",
        "risk_cause": "화기관리 미흡",
        "countermeasure": "화기감시자 배치, 소화기 비치",
        "risk_f": 2,
        "risk_s": 5,
        "risk_r": 10,
        "keywords": ["용접", "절단", "화재"],
    },
    {
        "work_category": "공통",
        "trade_type": "고소작업",
        "risk_factor": "개구부 추락",
        "risk_cause": "덮개 미설치/난간 미비",
        "countermeasure": "개구부 덮개 설치, 안전난간 설치",
        "risk_f": 3,
        "risk_s": 5,
        "risk_r": 15,
        "keywords": ["고소", "개구부", "추락"],
    },
]


def main() -> None:
    # FK 대상 메타데이터 등록
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401

    db = SessionLocal()
    try:
        for sample in SAMPLES:
            item = RiskLibraryItem(
                source_scope="HQ_STANDARD",
                owner_site_id=None,
                is_active=True,
            )
            db.add(item)
            db.flush()

            rev = RiskLibraryItemRevision(
                item_id=item.id,
                revision_no=1,
                is_current=True,
                effective_from=date.today(),
                effective_to=None,
                work_category=sample["work_category"],
                trade_type=sample["trade_type"],
                risk_factor=sample["risk_factor"],
                risk_cause=sample["risk_cause"],
                countermeasure=sample["countermeasure"],
                risk_f=sample["risk_f"],
                risk_s=sample["risk_s"],
                risk_r=sample["risk_r"],
                revised_by_user_id=None,
                revised_at=utc_now(),
                revision_note="seed sample",
            )
            db.add(rev)
            db.flush()

            for kw in sample["keywords"]:
                db.add(
                    RiskLibraryKeyword(
                        risk_revision_id=rev.id,
                        keyword=kw.lower(),
                        weight=1.0,
                    )
                )
        db.commit()
        print(f"seeded risk samples: {len(SAMPLES)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
