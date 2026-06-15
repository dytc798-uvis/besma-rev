import { ref } from "vue";
import { api } from "@/services/api";
import { isFeGuidePreview, getFeGuideScene } from "@/utils/feGuidePreview";
import { readConsentCached, writeConsentCached } from "@/utils/feSessionCache";
import { useAuthStore } from "@/stores/auth";

/** /functional-eval/consent/status 응답 중 FeConsentGate에 전달할 필드 */
export interface FeConsentPrefill {
  consent_body?: string;
  consent_title?: string;
  consent_kind?: string;
  role_line?: string;
  team_label?: string;
  site_full_name?: string;
  evaluation_open?: boolean;
  evaluation_opens_at_label?: string;
}

export function useFeConsentCheck() {
  const consentLoading = ref(true);
  const consentRequired = ref(false);
  const consentPrefill = ref<FeConsentPrefill | null>(null);

  const consentSignedAtLabel = ref("");
  const evaluationOpen = ref(true);
  const evaluationOpensAtLabel = ref("");

  async function checkConsent() {
    const auth = useAuthStore();
    const loginId = (auth.user?.login_id || "").trim();

    if (loginId && readConsentCached(loginId)) {
      consentRequired.value = false;
      consentLoading.value = false;
      void refreshConsentInBackground(loginId);
      return;
    }

    consentLoading.value = true;
    if (isFeGuidePreview()) {
      if (getFeGuideScene() === "consent") {
        consentRequired.value = true;
        try {
          const res = await api.get("/functional-eval/consent/status");
          consentPrefill.value = res.data as FeConsentPrefill;
        } catch {
          consentPrefill.value = null;
        }
      } else {
        consentRequired.value = false;
      }
      consentLoading.value = false;
      return;
    }
    await refreshConsentInBackground(loginId);
  }

  async function refreshConsentInBackground(loginId: string) {
    const showBlockingLoader = consentLoading.value;
    if (!showBlockingLoader) {
      consentLoading.value = false;
    }
    try {
      const res = await api.get("/functional-eval/consent/status");
      consentRequired.value = Boolean(res.data.required);
      evaluationOpen.value = res.data.evaluation_open !== false;
      evaluationOpensAtLabel.value = res.data.evaluation_opens_at_label || "";
      consentPrefill.value = res.data as FeConsentPrefill;
      consentSignedAtLabel.value = res.data.signed_at_label || res.data.signed_at || "";
      if (loginId && !consentRequired.value) {
        writeConsentCached(loginId, true);
      }
    } catch {
      if (showBlockingLoader) {
        consentRequired.value = false;
      }
      consentPrefill.value = null;
      consentSignedAtLabel.value = "";
    } finally {
      consentLoading.value = false;
    }
  }

  function onConsentCompleted() {
    consentRequired.value = false;
    const loginId = (useAuthStore().user?.login_id || "").trim();
    if (loginId) writeConsentCached(loginId, true);
  }

  return {
    consentLoading,
    consentRequired,
    consentPrefill,
    consentSignedAtLabel,
    evaluationOpen,
    evaluationOpensAtLabel,
    checkConsent,
    onConsentCompleted,
  };
}
