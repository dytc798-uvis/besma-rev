"""현장 목록 정렬: 데모/운영에서 우선 노출할 site_code 를 앞에 둔다."""

from sqlalchemy import case

from app.modules.sites.models import Site

# seed_data 기준: SITE002 = 파일럿(청라 C18BL), SITE001 = 현대엔지니어링(화성 기아)
PRIORITY_SITE_CODES = ("SITE002", "SITE001")


def site_list_priority_order():
    return case(
        # 주소가 채워진 청라 C18 항목을 최우선으로 노출
        (
            ((Site.site_name.contains("C18BL")) | (Site.site_name.contains("청라C18")))
            & Site.address.isnot(None)
            & (Site.address != ""),
            0,
        ),
        (Site.site_code == "SITE002", 1),
        (Site.site_code == "SITE001", 2),
        else_=3,
    )
