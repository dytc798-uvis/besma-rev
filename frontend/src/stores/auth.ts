import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api } from "@/services/api";

export interface AuthUser {
  id: number;
  name: string;
  login_id: string;
  role: string;
  must_change_password: boolean;
  ui_type: "HQ_SAFE" | "SITE" | "HQ_OTHER";
  site_id: number | null;
  person_id: number | null;
  map_preference?: "NAVER" | "TMAP" | null;
}

export type TestPersona = "HQ_ADMIN" | "SITE_MANAGER" | "WORKER";

const TEST_PERSONA_STORAGE_KEY = "besma_test_persona";
const TEST_SITE_CONTEXT_STORAGE_KEY = "besma_test_site_context_id";
const rawSiteContextId = localStorage.getItem(TEST_SITE_CONTEXT_STORAGE_KEY);
const initialSiteContextId = rawSiteContextId && Number.isFinite(Number(rawSiteContextId))
  ? Number(rawSiteContextId)
  : null;

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(localStorage.getItem("besma_token"));
  const user = ref<AuthUser | null>(null);
  const selectedPersona = ref<TestPersona | null>(
    (localStorage.getItem(TEST_PERSONA_STORAGE_KEY) as TestPersona | null) ?? null,
  );
  const testSiteContextId = ref<number | null>(
    initialSiteContextId && initialSiteContextId > 0 ? initialSiteContextId : null,
  );

  const isAuthenticated = computed(() => !!token.value && !!user.value);
  const mustChangePassword = computed(() => !!user.value?.must_change_password);
  const isTestPersonaMode = computed(() => import.meta.env.DEV);
  const effectivePersona = computed<TestPersona | null>(() => {
    if (!isTestPersonaMode.value) return null;
    return selectedPersona.value;
  });
  const effectiveUiType = computed<"HQ_SAFE" | "SITE" | "HQ_OTHER" | null>(() => {
    if (!isTestPersonaMode.value || !effectivePersona.value) {
      return user.value?.ui_type ?? null;
    }
    if (effectivePersona.value === "HQ_ADMIN") return "HQ_SAFE";
    if (effectivePersona.value === "SITE_MANAGER") return "SITE";
    return "SITE";
  });
  const effectiveSiteId = computed<number | null>(() => {
    if (user.value?.site_id) return user.value.site_id;
    if (isTestPersonaMode.value && effectivePersona.value === "SITE_MANAGER") {
      return testSiteContextId.value;
    }
    return user.value?.site_id ?? null;
  });

  async function login(loginId: string, password: string) {
    const form = new URLSearchParams();
    form.append("username", loginId);
    form.append("password", password);

    const res = await api.post("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    token.value = res.data.access_token;
    localStorage.setItem("besma_token", token.value!);
    await loadMe();
  }

  async function loadMe() {
    if (!token.value) return;
    const res = await api.get("/auth/me");
    user.value = res.data as AuthUser;
  }

  function logout() {
    token.value = null;
    user.value = null;
    selectedPersona.value = null;
    testSiteContextId.value = null;
    localStorage.removeItem("besma_token");
    localStorage.removeItem(TEST_PERSONA_STORAGE_KEY);
    localStorage.removeItem(TEST_SITE_CONTEXT_STORAGE_KEY);
  }

  function setPersona(persona: TestPersona) {
    selectedPersona.value = persona;
    localStorage.setItem(TEST_PERSONA_STORAGE_KEY, persona);
  }

  function clearPersona() {
    selectedPersona.value = null;
    localStorage.removeItem(TEST_PERSONA_STORAGE_KEY);
  }

  function setTestSiteContext(siteId: number | null) {
    if (!siteId || !Number.isFinite(siteId) || siteId <= 0) {
      testSiteContextId.value = null;
      localStorage.removeItem(TEST_SITE_CONTEXT_STORAGE_KEY);
      return;
    }
    testSiteContextId.value = siteId;
    localStorage.setItem(TEST_SITE_CONTEXT_STORAGE_KEY, String(siteId));
  }

  return {
    token,
    user,
    isAuthenticated,
    mustChangePassword,
    isTestPersonaMode,
    effectivePersona,
    effectiveUiType,
    selectedPersona,
    testSiteContextId,
    effectiveSiteId,
    login,
    loadMe,
    logout,
    setPersona,
    clearPersona,
    setTestSiteContext,
  };
});

