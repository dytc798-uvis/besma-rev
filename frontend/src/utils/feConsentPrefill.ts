import type { FeConsentPrefill } from "@/composables/useFeConsentCheck";

export function applyFeConsentPrefill(
  data: FeConsentPrefill | null | undefined,
  targets: {
    consentBody: { value: string };
    consentTitle?: { value: string };
    teamLabel: { value: string };
    siteFullName: { value: string };
  },
) {
  if (!data) return;
  targets.consentBody.value = data.consent_body || "";
  if (targets.consentTitle && data.consent_title) {
    targets.consentTitle.value = data.consent_title;
  }
  targets.teamLabel.value = data.role_line || data.team_label || "";
  targets.siteFullName.value = data.site_full_name || "";
}

export const FE_CONSENT_FALLBACK_BODY =
  "본인은 BESMA 기능인인정제 평가 업무를 수행함에 있어 아래 사항을 확인하고 동의합니다.";
