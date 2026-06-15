import type { FeConsentPrefill } from "@/composables/useFeConsentCheck";

export function applyFeConsentPrefill(
  data: FeConsentPrefill | null | undefined,
  targets: {
    consentBody: { value: string };
    teamLabel: { value: string };
    siteFullName: { value: string };
  },
) {
  if (!data) return;
  targets.consentBody.value = data.consent_body || "";
  targets.teamLabel.value = data.role_line || data.team_label || "";
  targets.siteFullName.value = data.site_full_name || "";
}

export const FE_CONSENT_FALLBACK_BODY =
  "기능인인정제 평가 업무 수행에 동의합니다.";
