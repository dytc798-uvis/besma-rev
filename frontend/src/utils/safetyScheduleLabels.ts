/**
 * 안전인정제 캘린더 셀용 짧은 라벨 (전체 제목은 상세/툴팁).
 */
export function shortSafetyScheduleLabel(raw: string): string {
  const t = raw
    .replace(/^\s*\d+[.,]\s*/, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!t) return raw.trim();

  if (/SHUT\s*DOWN|셧다운/i.test(t)) return "현장 SHUT DOWN";
  if (/부처님|부처님오신/i.test(t)) return "부처님 오신 날";
  if (/대체\s*휴일/.test(t)) return "대체 휴일";
  if (/대표이사\s*안전점검|대표이사/.test(t)) return "대표이사 점검";
  if (/공사임원\s*점검|공사임원/.test(t)) return "공사임원 점검";
  if (/안전실\s*임원\s*점검|안전실\s*임원점검|안전실\s*임원/.test(t)) return "안전실 임원점검";
  if (/안전보건실\s*점검|안전보건실\s*장\s*점검/.test(t)) return "안전실 점검";
  if (/안전보건경영회의\s*준비|경영회의\s*준비/.test(t)) return "경영회의 준비";
  if (/안전보건경영회의/.test(t)) return "안전보건경영회의";
  if (/월간\s*제출|제출자료\s*취합/.test(t)) return "월간자료 취합";
  if (/안전담당자\s*채용|삼성인정제\s*안전담당자/.test(t)) return "안전담당자 채용";
  if (/이행확인\s*점검/.test(t)) return "이행확인 점검";
  if (/삼성인정제\s*본사\s*이행|본사\s*이행항목|이행항목\s*검토/.test(t)) return "본사 이행항목 검토";
  if (/삼성인정제\s*샘플\s*현장|샘플\s*현장\s*운영/.test(t)) return "샘플 현장 운영";
  if (/청라\s*C18|C18\s*현장점검|현장점검/.test(t)) return "C18 현장점검";
  if (/본사\s*회의/.test(t)) return "본사 회의";
  if (/현장\s*운영\s*종료/.test(t)) return "현장 운영 종료";
  if (/의견청취|포스터\s*배포|비상대응|서류양식|싸이클|가이드/.test(t)) return "현장 착수 점검·배포";

  const first = t.split("\n")[0]?.trim() ?? t;
  return first.length > 22 ? `${first.slice(0, 20)}…` : first;
}
