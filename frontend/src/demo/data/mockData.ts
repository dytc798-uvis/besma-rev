export const siteSummary = [
  { name: "부현전기 서울 현장", submitRate: 92, pending: 1, linkedWorkers: 1 },
  { name: "부현전기 부산 현장", submitRate: 86, pending: 2, linkedWorkers: 1 },
  { name: "[1.DL건설] 전도관구역 주택재개발 정비사업조합(01공구)", submitRate: 74, pending: 5, linkedWorkers: 0 },
  { name: "[1.대우건설] 강릉비행장현장 특고압 전력 및 통신 지장물 이설공사", submitRate: 68, pending: 7, linkedWorkers: 0 },
];

export const workers = [
  {
    name: "강근원",
    site: "부현전기 서울 현장",
    status: "작업가능",
    affiliationType: "DB 연계",
    note: "당일 출역 예정",
  },
  {
    name: "강익종",
    site: "부현전기 부산 현장",
    status: "미교육",
    affiliationType: "DB 연계",
    note: "신규 안전교육 필요",
  },
  {
    name: "강태원",
    site: "소속 미연결",
    status: "미확인",
    affiliationType: "site_code 미반영",
    note: "현장코드 확인 필요",
  },
  {
    name: "강현석",
    site: "소속 미연결",
    status: "작업가능",
    affiliationType: "site_code 미반영",
    note: "소속 매핑 대기",
  },
  {
    name: "고유빈",
    site: "[1.DL건설] 전도관구역 주택재개발 정비사업조합(01공구)",
    status: "작업가능",
    affiliationType: "DB 연계",
    note: "투입 확정",
  },
  {
    name: "곽상우",
    site: "소속 미연결",
    status: "미교육",
    affiliationType: "site_code 미반영",
    note: "기초교육 미완료",
  },
  {
    name: "김기배",
    site: "[1.대우건설] 강릉비행장현장 특고압 전력 및 통신 지장물 이설공사",
    status: "작업가능",
    affiliationType: "DB 연계",
    note: "야간 작업 가능",
  },
  {
    name: "김대호",
    site: "소속 미연결",
    status: "미확인",
    affiliationType: "site_code 미반영",
    note: "신상 확인 대기",
  },
];

export const works = [
  {
    site: "부현전기 서울 현장",
    worker: "근로자1",
    task: "전기 케이블 포설",
    risk: "감전",
    countermeasure: "절연보호구 착용, 차단기 확인",
  },
  {
    site: "부현전기 부산 현장",
    worker: "근로자2",
    task: "분전반 점검",
    risk: "아크 발생",
    countermeasure: "무전압 확인 후 점검",
  },
  {
    site: "[1.DL건설] 전도관구역 주택재개발 정비사업조합(01공구)",
    worker: "강근원",
    task: "가설 전원 정리",
    risk: "넘어짐",
    countermeasure: "통로 정리 및 케이블 고정",
  },
];

export const documents = [
  { site: "부현전기 서울 현장", name: "작업계획서", status: "완료", reason: "-" },
  { site: "부현전기 부산 현장", name: "TBM 회의록", status: "미완료", reason: "현장 업로드 대기" },
  {
    site: "[1.대우건설] 강릉비행장현장 특고압 전력 및 통신 지장물 이설공사",
    name: "위험성평가서",
    status: "반려",
    reason: "서명 누락",
  },
];
