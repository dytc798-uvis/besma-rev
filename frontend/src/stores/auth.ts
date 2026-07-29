import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { api } from "@/services/api";

export interface AuthUser {
  id: number;
  name: string;
  login_id: string;
  role: string;
  must_change_password: boolean;
  needs_fe_consent?: boolean;
  fe_consent_required?: boolean;
  ui_type: "HQ_SAFE" | "SITE" | "HQ_OTHER";
  site_id: number | null;
  person_id: number | null;
  map_preference?: "NAVER" | "TMAP" | null;
  can_system_backup?: boolean;
}

export type TestPersona = "HQ_ADMIN" | "SITE_MANAGER" | "WORKER";

const TEST_PERSONA_STORAGE_KEY = "besma_test_persona";
const TEST_SITE_CONTEXT_STORAGE_KEY = "besma_test_site_context_id";

function readStorageItem(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorageItem(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore quota / private mode */
  }
}

function removeStorageItem(key: string) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

const rawSiteContextId = readStorageItem(TEST_SITE_CONTEXT_STORAGE_KEY);
const initialSiteContextId = rawSiteContextId && Number.isFinite(Number(rawSiteContextId))
  ? Number(rawSiteContextId)
  : null;

const SESSION_BOOTSTRAP_TIMEOUT_MS = 12_000;

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(readStorageItem("besma_token"));
  const user = ref<AuthUser | null>(null);
  const sessionBootstrapped = ref(!token.value);
  let bootstrapPromise: Promise<void> | null = null;
  let authGeneration = 0;
  const selectedPersona = ref<TestPersona | null>(
    (readStorageItem(TEST_PERSONA_STORAGE_KEY) as TestPersona | null) ?? null,
  );
  const testSiteContextId = ref<number | null>(
    initialSiteContextId && initialSiteContextId > 0 ? initialSiteContextId : null,
  );

  const isAuthenticated = computed(() => !!token.value && !!user.value);
  const mustChangePassword = computed(() => !!user.value?.must_change_password);
  const needsFeConsent = computed(() => !!user.value?.needs_fe_consent);
  const feConsentRequired = computed(() => !!user.value?.fe_consent_required);
  const needsFeOnboarding = computed(() => needsFeConsent.value && feConsentRequired.value);
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

  function bumpAuthGeneration() {
    authGeneration += 1;
    return authGeneration;
  }

  function cancelInFlightSessionWork() {
    bumpAuthGeneration();
    bootstrapPromise = null;
    sessionBootstrapped.value = true;
  }

  /** 로그인 화면 진입 시 — 백그라운드 세션 복구가 새 로그인과 겹치지 않게 */
  function prepareLoginPage() {
    cancelInFlightSessionWork();
    user.value = null;
    token.value = null;
    removeStorageItem("besma_token");
  }

  async function login(loginId: string, password: string) {
    const loginGeneration = bumpAuthGeneration();
    bootstrapPromise = null;
    user.value = null;
    token.value = null;
    removeStorageItem("besma_token");
    sessionBootstrapped.value = true;

    const normalizedId = loginId.trim();
    const normalizedPassword = password.trim();
    const form = new URLSearchParams();
    form.append("username", normalizedId);
    form.append("password", normalizedPassword);

    const res = await api.post("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      timeout: 20_000,
    });

    if (loginGeneration !== authGeneration) {
      throw new Error("LOGIN_SUPERSEDED");
    }

    token.value = res.data.access_token;
    writeStorageItem("besma_token", token.value!);
    sessionBootstrapped.value = false;

    try {
      await loadMe({ skipAuthRedirect: true, generation: loginGeneration });
      if (loginGeneration !== authGeneration) {
        throw new Error("LOGIN_SUPERSEDED");
      }
      sessionBootstrapped.value = true;
    } catch (err) {
      if (loginGeneration === authGeneration) {
        token.value = null;
        user.value = null;
        removeStorageItem("besma_token");
        sessionBootstrapped.value = true;
      }
      throw err;
    }
  }

  async function bootstrapSession() {
    if (sessionBootstrapped.value) return;
    if (bootstrapPromise) {
      await bootstrapPromise;
      return;
    }
    if (!token.value) {
      sessionBootstrapped.value = true;
      return;
    }

    const bootstrapGeneration = authGeneration;
    bootstrapPromise = (async () => {
      try {
        await Promise.race([
          loadMe({ skipAuthRedirect: true, generation: bootstrapGeneration }),
          new Promise<never>((_, reject) => {
            setTimeout(() => reject(new Error("SESSION_BOOTSTRAP_TIMEOUT")), SESSION_BOOTSTRAP_TIMEOUT_MS);
          }),
        ]);
      } catch {
        if (bootstrapGeneration === authGeneration && token.value) {
          logout();
        }
      } finally {
        if (bootstrapGeneration === authGeneration) {
          sessionBootstrapped.value = true;
        }
        if (bootstrapPromise && bootstrapGeneration === authGeneration) {
          bootstrapPromise = null;
        }
      }
    })();
    await bootstrapPromise;
  }

  async function loadMe(options?: { skipAuthRedirect?: boolean; generation?: number }) {
    const tokenAtStart = token.value;
    if (!tokenAtStart) return;

    const res = await api.get("/auth/me", {
      skipAuthRedirect: options?.skipAuthRedirect ?? false,
    });

    if (options?.generation != null && options.generation !== authGeneration) return;
    if (token.value !== tokenAtStart) return;

    user.value = res.data as AuthUser;
  }

  function logout() {
    bumpAuthGeneration();
    token.value = null;
    user.value = null;
    selectedPersona.value = null;
    testSiteContextId.value = null;
    sessionBootstrapped.value = true;
    bootstrapPromise = null;
    removeStorageItem("besma_token");
    removeStorageItem(TEST_PERSONA_STORAGE_KEY);
    removeStorageItem(TEST_SITE_CONTEXT_STORAGE_KEY);
  }

  function setPersona(persona: TestPersona) {
    selectedPersona.value = persona;
    writeStorageItem(TEST_PERSONA_STORAGE_KEY, persona);
  }

  function clearPersona() {
    selectedPersona.value = null;
    removeStorageItem(TEST_PERSONA_STORAGE_KEY);
  }

  function setTestSiteContext(siteId: number | null) {
    if (!siteId || !Number.isFinite(siteId) || siteId <= 0) {
      testSiteContextId.value = null;
      removeStorageItem(TEST_SITE_CONTEXT_STORAGE_KEY);
      return;
    }
    testSiteContextId.value = siteId;
    writeStorageItem(TEST_SITE_CONTEXT_STORAGE_KEY, String(siteId));
  }

  return {
    token,
    user,
    isAuthenticated,
    mustChangePassword,
    needsFeConsent,
    feConsentRequired,
    needsFeOnboarding,
    isTestPersonaMode,
    effectivePersona,
    effectiveUiType,
    selectedPersona,
    testSiteContextId,
    effectiveSiteId,
    sessionBootstrapped,
    prepareLoginPage,
    login,
    loadMe,
    bootstrapSession,
    logout,
    setPersona,
    clearPersona,
    setTestSiteContext,
  };
});
