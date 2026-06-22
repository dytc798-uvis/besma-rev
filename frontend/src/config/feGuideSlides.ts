/** 기능인인정제 설명 — 슬라이드 정의 (캡처는 UI 요소 단위, 강조 오버레이 없음) */

export type FeGuideImageLayout = "single" | "dual" | "triple" | "phone-reward";

export interface FeGuideImageItem {
  src: string;
  label?: string;
  /** true면 설명 페이지에서 핸드폰 프레임으로 표시 */
  phoneFrame?: boolean;
}

export type FeGuideImage = string | FeGuideImageItem;

export interface FeGuideSlide {
  title: string;
  bullets: string[];
  images?: FeGuideImage[];
  layout?: FeGuideImageLayout;
}

const IMG = "/fe-guide/screenshots";

function img(file: string, opts: Omit<FeGuideImageItem, "src"> = {}): FeGuideImageItem {
  return { src: `${IMG}/${file}`, ...opts };
}

export function normalizeGuideImages(images?: FeGuideImage[]): FeGuideImageItem[] {
  return (images ?? []).map((item) => (typeof item === "string" ? { src: item } : item));
}

export const FE_GUIDE_SLIDES: Record<string, FeGuideSlide[]> = {
  팀장용: [
    {
      title: "1. 부여된 아이디로 로그인합니다.",
      bullets: [
        "아이디: 대우청라-김팀장    비밀번호: ●●●●●●",
        "비밀번호는 주민등록번호 앞 6자리입니다.",
      ],
      images: [img("login_team.png")],
      layout: "single",
    },
    {
      title: "2. 기능인인정제 평가 동의서를 읽고 서명합니다.",
      bullets: [
        "최초 1회만 표시됩니다. 동의문 확인 후 체크 · 서명 · 「동의 및 서명」",
        "서명 완료 후에는 다시 표시되지 않습니다.",
      ],
      images: [img("fe-onboarding-password-consent-modal.png")],
      layout: "single",
    },
    {
      title: "3. 팀장은 담당 팀원을 평가합니다.",
      bullets: [
        "팀장은 핸드폰으로 기능·안전 항목별 등급을 선택합니다.",
        "3-1. 마지막 평가항목까지 입력하면 자동 저장됩니다.",
        "3-2. 포상은 「포상」 버튼 → 사진 업로드(본사 승인 후 가점 반영).",
        "3-3. 제재 등록 시 근거(사진/텍스트)+서명. 등록 후 수정 불가.",
      ],
      images: [
        img("team_evaluate_mobile.png", { phoneFrame: true }),
        img("reward_upload_modal.png", { label: "포상 사진 업로드" }),
        img("reward_evidence_kimposang.png", { label: "제출된 포상 사진" }),
      ],
      layout: "phone-reward",
    },
    {
      title: "4. 평가 완료 후 「평가완료보고서 서명」",
      bullets: [
        "담당 팀원 전원 평가 완료 후 버튼이 활성화됩니다.",
        "서명하면 보고서가 저장되며, 이후 평가·포상·제재 수정이 불가합니다.",
      ],
      images: [img("team_signoff_modal.png")],
      layout: "single",
    },
    {
      title: "5. 본사 안전보건실 검토",
      bullets: ["소장 제출 후 본사에서 포상 승인·제재·점수를 검토·기록합니다."],
      images: [img("hq_dashboard.png")],
      layout: "single",
    },
    {
      title: "6. 안전보건실장 승인",
      bullets: [
        "안전보건실장이 현장 평가보고서를 확인합니다.",
        "「일괄 최종승인」 또는 현장별 「최종승인」 버튼을 누릅니다.",
      ],
      images: [img("hq_director_approval.png")],
      layout: "single",
    },
    {
      title: "7. 대표님 최종 승인",
      bullets: [
        "대표님 「대표이사 최종승인 서명」으로 평가가 확정됩니다.",
        "승인본은 서명과 함께 전체 현황을 출력할 수 있습니다.",
      ],
      images: [img("ceo_approval.png")],
      layout: "single",
    },
  ],
  소장용: [
    {
      title: "1. 부여된 아이디로 로그인합니다.",
      bullets: [
        "아이디: 대우청라-박명식    비밀번호: ●●●●●●",
        "비밀번호는 주민등록번호 앞 6자리입니다.",
      ],
      images: [img("login_manager.png")],
      layout: "single",
    },
    {
      title: "2. 기능인인정제 평가 동의서를 읽고 서명합니다.",
      bullets: ["최초 1회 동의·서명 후 기능인제 업무를 수행합니다."],
      images: [img("fe-onboarding-password-consent-modal.png")],
      layout: "single",
    },
    {
      title: "3. 소장은 직영근로자 및 팀장을 평가합니다.",
      bullets: [
        "직영 근로자는 소장이 직접 평가합니다. 팀원은 팀장 평가 후 보고서를 검토합니다.",
        "3-1. 마지막 평가항목 입력 시 자동 저장됩니다.",
        "3-2. 포상은 사진 업로드(본사 승인). 제재는 근거+서명 필수.",
      ],
      images: [
        img("manager_roster.png"),
        img("reward_upload_modal.png", { label: "포상 사진 업로드" }),
        img("reward_evidence_kimposang.png", { label: "제출된 포상 사진" }),
      ],
      layout: "phone-reward",
    },
    {
      title: "4. 평가 완료 후 평가보고서 서명·제출",
      bullets: [
        "팀장 보고서 전원 확인 → 「평가완료보고서 제출 및 서명」",
        "서명 후 현장 평가·포상·제재 수정 불가",
      ],
      images: [img("manager_approval.png")],
      layout: "single",
    },
    {
      title: "5. 본사 안전보건실 검토",
      bullets: [
        "소장 제출 후 본사에서 포상 승인·제재·점수를 검토·기록합니다.",
        "필요 시 추가 포상·제재 사항을 검토하고 기록합니다.",
      ],
      images: [img("hq_dashboard.png")],
      layout: "single",
    },
    {
      title: "6. 안전보건실장 승인",
      bullets: [
        "안전보건실장이 현장 평가보고서를 확인하고 승인·서명합니다.",
        "「일괄 최종승인」 또는 현장별 「최종승인」 버튼을 누릅니다.",
      ],
      images: [img("hq_director_approval.png")],
      layout: "single",
    },
    {
      title: "7. 대표님 최종 승인",
      bullets: [
        "대표님 최종 승인·서명 후 평가가 확정됩니다.",
        "승인본은 서명과 함께 전체 현황을 PDF·등급표로 출력할 수 있습니다.",
      ],
      images: [img("ceo_approval.png")],
      layout: "single",
    },
  ],
  "본사·대표님용": [
    {
      title: "1. 부여된 아이디로 로그인합니다.",
      bullets: [
        "안전보건실: 안전보건-조동문 / ●●●●●●",
        "대표님: 부현대표-김홍수 / ●●●●●●",
        "비밀번호는 주민등록번호 앞 6자리입니다.",
      ],
      images: [img("login_hq.png")],
      layout: "single",
    },
    {
      title: "2. 기능인인정제 평가 동의서(최초 1회)",
      bullets: ["본사·대표 계정도 최초 접속 시 동의·서명이 필요합니다."],
      images: [img("fe-onboarding-password-consent-modal.png")],
      layout: "single",
    },
    {
      title: "3. 현장 평가 결과 확인",
      bullets: [
        "현장별 평가 진행·제출 상태를 확인합니다.",
        "소장이 현장에서 제출한 후 본사에서 검토합니다.",
      ],
      images: [img("hq_dashboard.png")],
      layout: "single",
    },
    {
      title: "4. 평가보고서 서명 완료 확인",
      bullets: [
        "현장에서 팀장·소장 서명이 완료된 보고서가 본사로 전달됩니다.",
        "서명 완료 후 현장에서는 평가·포상·제재를 수정할 수 없습니다.",
      ],
      images: [img("manager_approval.png")],
      layout: "single",
    },
    {
      title: "5. 포상 승인 · 제재 검토·기록",
      bullets: [
        "현장에서 제출한 포상 사진을 승인합니다(가점 반영).",
        "필요 시 근로자별 「제재」 등록(근거+서명, 수정 불가).",
        "점수 이견 시 평가 점수를 수정하고 사유를 기록합니다.",
      ],
      images: [
        img("reward_evidence_kimposang.png", { label: "포상 사진" }),
        img("sanction_evidence_kimbusil.png", { label: "제재 근거" }),
      ],
      layout: "dual",
    },
    {
      title: "6. 안전보건실장 승인",
      bullets: [
        "검토 후 「일괄 최종승인」 또는 현장별 「최종승인」을 누릅니다.",
        "승인·서명 후 대표님 최종 승인 단계로 넘어갑니다.",
      ],
      images: [img("hq_director_approval.png")],
      layout: "single",
    },
    {
      title: "7. 대표님 최종 승인 · 전체 현황 출력",
      bullets: [
        "대표님 「대표이사 최종승인 서명」으로 평가가 확정됩니다.",
        "승인본 PDF·등급표로 전체 현황을 출력·보관할 수 있습니다.",
      ],
      images: [img("ceo_approval.png")],
      layout: "single",
    },
  ],
};
