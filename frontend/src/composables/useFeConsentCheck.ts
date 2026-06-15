import { ref } from "vue";
import { api } from "@/services/api";
import { isFeGuidePreview } from "@/utils/feGuidePreview";

/** /functional-eval/consent/status 응답 중 FeConsentGate에 전달할 필드 */
export interface FeConsentPrefill {
  consent_body?: string;
  role_line?: string;
  team_label?: string;
  site_full_name?: string;
}

export function useFeConsentCheck() {
  const consentLoading = ref(true);
  const consentRequired = ref(false);
  const consentPrefill = ref<FeConsentPrefill | null>(null);

  const consentSignedAtLabel = ref("");

  async function checkConsent() {
    consentLoading.value = true;
    if (isFeGuidePreview()) {
      consentRequired.value = false;
      consentLoading.value = false;
      return;
    }
    try {
      const res = await api.get("/functional-eval/consent/status");
      consentRequired.value = Boolean(res.data.required);
      consentPrefill.value = res.data as FeConsentPrefill;
      consentSignedAtLabel.value = res.data.signed_at_label || res.data.signed_at || "";
    } catch {
      consentRequired.value = false;
      consentPrefill.value = null;
      consentSignedAtLabel.value = "";
    } finally {
      consentLoading.value = false;
    }
  }

  function onConsentCompleted() {
    consentRequired.value = false;
  }

  return {
    consentLoading,
    consentRequired,
    consentPrefill,
    consentSignedAtLabel,
    checkConsent,
    onConsentCompleted,
  };
}
