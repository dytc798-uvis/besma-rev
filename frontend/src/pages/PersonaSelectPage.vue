<template>
  <div class="preview-shell">
    <div class="preview-card">
      <p class="eyebrow">정상익 전용 검증모드</p>
      <h1>화면 관점 선택</h1>
      <p class="intro">
        실제 계정 권한과 데이터는 변경하지 않습니다. 검증모드에서는 조회만 가능하며
        저장·승인·서명·삭제 요청은 차단됩니다.
      </p>

      <label v-if="auth.user?.can_role_preview" class="site-field">
        <span>검증할 현장</span>
        <select v-model.number="selectedSiteId">
          <option :value="0">현장을 선택하세요</option>
          <option v-for="site in sites" :key="site.id" :value="site.id">
            {{ site.site_name }} · {{ site.site_code }}
          </option>
        </select>
      </label>
      <p v-if="error" class="error">{{ error }}</p>

      <div v-if="auth.user?.can_role_preview" class="persona-grid">
        <button class="persona site" type="button" @click="chooseSite('SITE_STAFF')">
          <strong>현장 담당자 입장</strong>
          <small>체감온도 입력·현장 업무 화면 확인</small>
        </button>
        <button class="persona manager" type="button" @click="chooseSite('SITE_MANAGER')">
          <strong>현장소장 입장</strong>
          <small>확인 대기·관리자 확인 화면 확인</small>
        </button>
        <button class="persona hq" type="button" @click="choose('HQ_OTHER')">
          <strong>본사 타부서 입장</strong>
          <small>조회 중심 메뉴와 화면 확인</small>
        </button>
      </div>

      <div v-else class="persona-grid">
        <button class="persona" type="button" @click="choose('HQ_ADMIN')">본사관리자</button>
        <button class="persona" type="button" @click="choose('SITE_MANAGER')">현장관리자</button>
        <button class="persona" type="button" @click="choose('WORKER')">근로자</button>
      </div>

      <div class="footer-actions">
        <button class="secondary" type="button" @click="logout">로그아웃</button>
        <button class="secondary" type="button" @click="goDefault">기존 본사 역할로 돌아가기</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
import { useAuthStore, type TestPersona } from "@/stores/auth";
import { siteMobileOrDesktopHomeName } from "@/utils/siteHomeRoute";
import { hqSafeHomeRouteName } from "@/utils/hqHomeRoute";

interface PreviewSite {
  id: number;
  site_code: string;
  site_name: string;
}

const auth = useAuthStore();
const router = useRouter();
const sites = ref<PreviewSite[]>([]);
const selectedSiteId = ref(auth.testSiteContextId ?? 0);
const error = ref("");

function routeByPersona(persona: TestPersona) {
  if (persona === "HQ_ADMIN") {
    router.push({ name: hqSafeHomeRouteName() });
    return;
  }
  if (persona === "HQ_OTHER") {
    router.push({ name: "hq-other-heat-stress" });
    return;
  }
  if (persona === "SITE_STAFF" || persona === "SITE_MANAGER") {
    router.push({ name: "site-heat-stress" });
    return;
  }
  router.push({ name: "worker-mobile-list" });
}

function choose(persona: TestPersona) {
  error.value = "";
  auth.setPersona(persona);
  routeByPersona(persona);
}

function chooseSite(persona: "SITE_STAFF" | "SITE_MANAGER") {
  if (!selectedSiteId.value) {
    error.value = "검증할 현장을 먼저 선택하세요.";
    return;
  }
  auth.setTestSiteContext(selectedSiteId.value);
  choose(persona);
}

function logout() {
  auth.logout();
  router.push({ name: "login" });
}

function goDefault() {
  auth.clearPersona();
  if (auth.user?.ui_type === "HQ_SAFE") {
    router.push({ name: hqSafeHomeRouteName() });
    return;
  }
  if (auth.user?.ui_type === "SITE") {
    router.push({ name: siteMobileOrDesktopHomeName() });
    return;
  }
  router.push({ name: "hq-other-heat-stress" });
}

onMounted(async () => {
  if (!auth.user?.can_role_preview) return;
  try {
    sites.value = (await api.get("/auth/role-preview/sites")).data;
  } catch {
    error.value = "현장 목록을 불러오지 못했습니다.";
  }
});
</script>

<style scoped>
.preview-shell{min-height:100vh;display:grid;place-items:center;padding:24px;background:linear-gradient(145deg,#eff6ff,#f8fafc 48%,#ecfeff)}
.preview-card{width:min(680px,100%);background:#fff;border:1px solid #dbe4ee;border-radius:24px;padding:30px;box-shadow:0 24px 70px rgba(15,23,42,.12)}
.eyebrow{margin:0;color:#0369a1;font-size:13px;font-weight:900;letter-spacing:.08em}.preview-card h1{margin:6px 0 8px}.intro{color:#475569;line-height:1.65;margin:0 0 20px}
.site-field{display:grid;gap:7px;font-weight:800;margin-bottom:18px}.site-field select{padding:12px;border:1px solid #cbd5e1;border-radius:11px;background:#fff;font:inherit}
.persona-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.persona{min-height:126px;border:1px solid #bfdbfe;border-radius:16px;background:#eff6ff;color:#1e3a8a;padding:18px;text-align:left;cursor:pointer}.persona strong,.persona small{display:block}.persona strong{font-size:17px}.persona small{margin-top:8px;line-height:1.45;color:#475569}.persona.manager{background:#f0fdfa;border-color:#99f6e4;color:#115e59}.persona.hq{background:#fff7ed;border-color:#fed7aa;color:#9a3412}
.footer-actions{display:flex;justify-content:space-between;gap:12px;margin-top:20px}.secondary{border:1px solid #cbd5e1;border-radius:10px;background:#fff;color:#334155;padding:10px 14px;font-weight:800;cursor:pointer}.error{color:#b91c1c;font-weight:800}
@media(max-width:680px){.preview-shell{padding:12px}.preview-card{padding:20px}.persona-grid{grid-template-columns:1fr}.persona{min-height:96px}.footer-actions{flex-direction:column}}
</style>
