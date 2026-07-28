<template>
  <div class="nsd-page">
    <header class="nsd-head">
      <h1>신규현장 배포 현황</h1>
      <p class="nsd-sub">
        예산견적팀 — 현장 기본정보 등록 · 외주구매팀 — 컨테이너 반입·안전 배포 체크 · 안전보건실 — 진행 확인
      </p>
      <p v-if="menuStatus.password_warning" class="nsd-warn">
        보안을 위해 초기 비밀번호(1111)를 변경해 주세요.
        <RouterLink to="/change-password">비밀번호 변경</RouterLink>
      </p>
    </header>

    <section v-if="canEditBudget" class="panel">
      <h2>{{ editingId ? "현장 수정" : "신규 현장 등록" }}</h2>
      <div class="nsd-form-grid">
        <label><span>도급사</span><input v-model="form.contractor" class="field-control" /></label>
        <label class="span2"><span>현장명</span><input v-model="form.site_name" class="field-control" required /></label>
        <label><span>공사금액(원)</span><input v-model="form.construction_amount" class="field-control" inputmode="numeric" /></label>
        <label><span>공사기간</span><input v-model="form.construction_period" class="field-control" placeholder="예: 2026.03~2027.02" /></label>
      </div>
      <div class="nsd-admin-section">
        <div class="nsd-admin-head">
          <span class="nsd-admin-title">관리자</span>
          <button type="button" class="stitch-btn-secondary nsd-add-btn" @click="addAdministrator">+ 추가</button>
        </div>
        <div v-if="!form.administrators.length" class="muted nsd-admin-empty">+ 버튼으로 소장·공무 등 관리자를 추가하세요.</div>
        <div v-for="(adm, idx) in form.administrators" :key="idx" class="nsd-admin-row">
          <select v-model="adm.role" class="field-control">
            <option v-for="opt in adminRoleOptions" :key="opt.key" :value="opt.key">{{ opt.label }}</option>
          </select>
          <input v-model="adm.name" class="field-control" placeholder="이름" />
          <button type="button" class="link-btn nsd-remove-btn" @click="removeAdministrator(idx)">삭제</button>
        </div>
      </div>
      <p v-if="previewRequirements.length" class="nsd-preview-req">
        <span v-for="lb in previewRequirements" :key="lb" class="nsd-req-label">{{ lb }}</span>
      </p>
      <p v-if="previewLogins.length" class="nsd-meta">예상 로그인 ID: {{ previewLogins.join(" · ") }}</p>
      <div class="actions">
        <button v-if="editingId" type="button" class="stitch-btn-secondary" @click="resetForm">취소</button>
        <button type="button" class="stitch-btn-primary" :disabled="saving || !form.site_name.trim()" @click="saveBudget">
          {{ saving ? "저장 중…" : editingId ? "수정 저장" : "현장 등록" }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </section>

    <section class="panel">
      <h2>현장 목록 <span class="count">({{ items.length }})</span></h2>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>현장명</th>
              <th>도급사</th>
              <th>금액</th>
              <th>소장/공무</th>
              <th>선임·지정</th>
              <th>배포</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in items" :key="row.id" :class="row.needs_highlight ? 'row-highlight--alert' : ''">
              <td>
                <strong>{{ row.site_name }}</strong>
                <div v-if="row.site_code" class="muted">{{ row.site_code }} · {{ row.site_alias }}</div>
              </td>
              <td>{{ row.contractor || "—" }}</td>
              <td>{{ formatAmount(row.construction_amount) }}</td>
              <td>
                <div v-if="canEditBudget">
                  <div v-if="adminNames(row, 'SITE_MANAGER').length">
                    <span v-for="(n, i) in adminNames(row, 'SITE_MANAGER')" :key="'m'+i">{{ n }}<span v-if="i < adminNames(row, 'SITE_MANAGER').length - 1">, </span></span>
                  </div>
                  <div v-else>—</div>
                  <div v-if="adminNames(row, 'GONGMU').length" class="muted">
                    <span v-for="(n, i) in adminNames(row, 'GONGMU')" :key="'g'+i">{{ n }}<span v-if="i < adminNames(row, 'GONGMU').length - 1">, </span></span>
                  </div>
                </div>
                <div v-else>—</div>
              </td>
              <td>
                <span v-for="lb in row.requirement_labels" :key="lb" class="nsd-req-label">{{ lb }}</span>
              </td>
              <td>
                <span :class="row.is_complete ? 'nsd-complete-badge' : 'nsd-pending-badge'">
                  {{ row.is_complete ? "완료" : "진행중" }}
                </span>
              </td>
              <td class="actions-cell">
                <button v-if="canEditBudget" type="button" class="link-btn" @click="editRow(row)">수정</button>
                <button type="button" class="link-btn" @click="selectRow(row)">상세</button>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="7" class="empty-cell">등록된 신규 현장이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="selected" class="panel">
      <h2>{{ selected.site_name }} — 배포·외주구매</h2>
      <div v-if="canEditProcurement" class="nsd-procurement">
        <label>
          <span>컨테이너 반입일 / 현장사무실 개설일</span>
          <input v-model="procurement.container_arrival_date" type="date" class="field-control" />
        </label>
        <div v-if="canEditSafetyChecks" class="nsd-checks">
          <h3>안전 배포 상황</h3>
          <label v-for="item in selected.safety_items" :key="item.key" class="check-row">
            <input v-model="procurement.safety_checks[item.key]" type="checkbox" />
            {{ item.label }}
          </label>
        </div>
        <p v-else-if="canEditProcurement" class="muted">안전 배포 체크는 신영석·주창오·공사관리팀 담당입니다.</p>
        <button type="button" class="stitch-btn-primary" :disabled="savingProc" @click="saveProcurement">외주구매 저장</button>
      </div>
      <div class="nsd-detail-grid">
        <div class="span2">
          <span class="lbl">관리자</span>
          <ul v-if="canEditBudget && selected.administrators?.length" class="nsd-admin-list">
            <li v-for="adm in selected.administrators" :key="adm.id">
              {{ adm.role_label }} — {{ adm.name }}
              <span v-if="adm.login_id" class="muted">({{ adm.login_id }})</span>
            </li>
          </ul>
          <span v-else>—</span>
        </div>
        <div><span class="lbl">컨테이너/개설</span> {{ selected.container_arrival_date || "—" }}</div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

interface AdminRoleOption {
  key: string;
  label: string;
}

interface DeploymentAdministrator {
  id?: number;
  role: string;
  role_label?: string;
  name: string;
  login_id?: string;
  sort_order?: number;
}

interface DeploymentItem {
  id: number;
  site_name: string;
  site_code?: string;
  site_alias: string;
  contractor?: string;
  construction_amount?: number;
  construction_period?: string;
  administrators?: DeploymentAdministrator[];
  admin_role_options?: AdminRoleOption[];
  site_manager_name?: string;
  gongmu_name?: string;
  safety_name?: string;
  construction_supervisor_name?: string;
  site_manager_login_id?: string;
  gongmu_login_id?: string;
  container_arrival_date?: string;
  requirement_labels: string[];
  safety_items: { key: string; label: string }[];
  safety_checks: Record<string, boolean>;
  is_complete: boolean;
  needs_highlight: boolean;
}

const DEFAULT_ADMIN_ROLES: AdminRoleOption[] = [
  { key: "SITE_MANAGER", label: "현장소장" },
  { key: "GONGMU", label: "공무" },
  { key: "SAFETY", label: "안전(관리자)" },
  { key: "CONSTRUCTION_SUPERVISOR", label: "공사(관리감독자)" },
  { key: "OTHER", label: "기타" },
];

const CONSTRUCTION_MANAGEMENT_LOGINS = [
  "공사관리-이재용",
  "공사관리-전용성",
  "공사관리-강태원",
  "공사관리-김종현",
  "공사관리-박성수",
];

const auth = useAuthStore();
const items = ref<DeploymentItem[]>([]);
const selected = ref<DeploymentItem | null>(null);
const menuStatus = ref({ incomplete_count: 0, needs_highlight: false, password_warning: false });
const editingId = ref<number | null>(null);
const saving = ref(false);
const savingProc = ref(false);
const error = ref("");

const form = reactive({
  contractor: "",
  site_name: "",
  construction_amount: "",
  construction_period: "",
  administrators: [] as { role: string; name: string }[],
});

const adminRoleOptions = computed(() => {
  const fromApi = items.value[0]?.admin_role_options;
  return fromApi?.length ? fromApi : DEFAULT_ADMIN_ROLES;
});

const procurement = reactive({
  container_arrival_date: "",
  safety_checks: {} as Record<string, boolean>,
});

const role = computed(() => auth.user?.role || "");
const isConstructionManagement = computed(() =>
  (auth.user?.department || "").trim().startsWith("공사관리"),
);
const canEditBudget = computed(
  () =>
    ["HQ_BUDGET_ESTIMATE", "HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(role.value) ||
    isConstructionManagement.value ||
    CONSTRUCTION_MANAGEMENT_LOGINS.includes(auth.user?.login_id || ""),
);
const canEditProcurement = computed(() =>
  ["HQ_OUTSOURCING_PURCHASE", "HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(role.value),
);
const canEditSafetyChecks = computed(() => {
  const login = auth.user?.login_id || "";
  return (
    ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(role.value) ||
    isConstructionManagement.value ||
    login === "외주구매-신영석" ||
    login === "외주구매-주창오" ||
    CONSTRUCTION_MANAGEMENT_LOGINS.includes(login)
  );
});

const previewRequirements = computed(() => {
  const amt = parseInt(String(form.construction_amount).replace(/[^\d]/g, ""), 10);
  const labels = ["관리감독자 지정 (모든 현장)"];
  if (!amt) return labels;
  if (amt >= 5_000_000_000) labels.unshift("안전보건관리책임자 선임 필요");
  else if (amt >= 2_000_000_000) labels.unshift("안전관리자 선임 필요");
  return labels;
});

const previewLogins = computed(() => {
  const ids: string[] = [];
  for (const adm of form.administrators) {
    const name = adm.name.trim();
    if (!name) continue;
    if (adm.role === "SITE_MANAGER" || adm.role === "GONGMU") {
      ids.push(`(별칭)-${name}`);
    }
  }
  return ids;
});

function adminNames(row: DeploymentItem, role: string) {
  const admins = row.administrators || [];
  return admins.filter((a) => a.role === role && a.name?.trim()).map((a) => a.name.trim());
}

function addAdministrator() {
  form.administrators.push({ role: "SITE_MANAGER", name: "" });
}

function removeAdministrator(idx: number) {
  form.administrators.splice(idx, 1);
}

function formatAmount(v?: number) {
  if (!v) return "—";
  return `${(v / 100_000_000).toFixed(1)}억`;
}

function resetForm() {
  editingId.value = null;
  Object.assign(form, {
    contractor: "", site_name: "", construction_amount: "", construction_period: "",
    administrators: [],
  });
}

function editRow(row: DeploymentItem) {
  editingId.value = row.id;
  const admins = (row.administrators || []).map((a) => ({ role: a.role, name: a.name }));
  Object.assign(form, {
    contractor: row.contractor || "",
    site_name: row.site_name,
    construction_amount: row.construction_amount ? String(row.construction_amount) : "",
    construction_period: row.construction_period || "",
    administrators: admins.length ? admins : [],
  });
}

function selectRow(row: DeploymentItem) {
  selected.value = row;
  procurement.container_arrival_date = row.container_arrival_date || "";
  procurement.safety_checks = { ...(row.safety_checks || {}) };
  for (const item of row.safety_items || []) {
    if (procurement.safety_checks[item.key] === undefined) procurement.safety_checks[item.key] = false;
  }
}

async function load() {
  const [listRes, menuRes] = await Promise.all([
    api.get("/new-site-deployment/deployments"),
    api.get("/new-site-deployment/menu-status"),
  ]);
  items.value = listRes.data.items || [];
  menuStatus.value = menuRes.data;
  if (selected.value) {
    const found = items.value.find((i) => i.id === selected.value!.id);
    if (found) selectRow(found);
  }
}

async function saveBudget() {
  saving.value = true;
  error.value = "";
  try {
    const administrators = form.administrators
      .map((a) => ({ role: a.role, name: a.name.trim() }))
      .filter((a) => a.name);
    const payload = {
      contractor: form.contractor,
      site_name: form.site_name,
      construction_amount: form.construction_amount,
      construction_period: form.construction_period,
      administrators,
    };
    if (editingId.value) {
      await api.put(`/new-site-deployment/deployments/${editingId.value}`, payload);
    } else {
      await api.post("/new-site-deployment/deployments", payload);
    }
    resetForm();
    await load();
    window.dispatchEvent(new CustomEvent("besma-nsd-updated"));
  } catch {
    error.value = "저장에 실패했습니다.";
  } finally {
    saving.value = false;
  }
}

async function saveProcurement() {
  if (!selected.value) return;
  savingProc.value = true;
  try {
    const payload: any = {
      container_arrival_date: procurement.container_arrival_date || null,
    };
    if (canEditSafetyChecks.value) {
      payload.safety_checks = procurement.safety_checks;
    }
    await api.put(`/new-site-deployment/deployments/${selected.value.id}/procurement`, payload);
    await load();
    window.dispatchEvent(new CustomEvent("besma-nsd-updated"));
  } finally {
    savingProc.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.nsd-page { max-width: 1200px; }
.nsd-head h1 { margin: 0 0 6px; }
.nsd-sub { color: #64748b; font-size: 14px; margin: 0 0 12px; }
.nsd-warn { background: #fff7ed; border: 1px solid #fdba74; padding: 10px 12px; border-radius: 8px; font-size: 14px; }
.nsd-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.nsd-form-grid .span2 { grid-column: span 2; }
.nsd-form-grid label span { display: block; font-size: 13px; color: #475569; margin-bottom: 4px; }
.nsd-admin-section { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.nsd-admin-head { display: flex; align-items: center; justify-content: space-between; }
.nsd-admin-title { font-size: 14px; font-weight: 600; color: #334155; }
.nsd-add-btn { padding: 4px 12px; font-size: 13px; }
.nsd-admin-row { display: grid; grid-template-columns: 160px 1fr auto; gap: 8px; align-items: center; }
.nsd-remove-btn { white-space: nowrap; }
.nsd-admin-empty { font-size: 13px; padding: 8px 0; }
.nsd-admin-list { margin: 4px 0 0; padding-left: 18px; font-size: 14px; }
.nsd-detail-grid .span2 { grid-column: span 2; }
.nsd-preview-req { margin: 10px 0; }
.nsd-meta { font-size: 13px; color: #64748b; }
.nsd-procurement { display: flex; flex-direction: column; gap: 12px; max-width: 480px; }
.nsd-checks { display: flex; flex-direction: column; gap: 6px; }
.check-row { display: flex; align-items: center; gap: 8px; font-size: 14px; }
.nsd-detail-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; font-size: 14px; margin-top: 12px; }
.lbl { color: #64748b; margin-right: 6px; }
.muted { color: #94a3b8; font-size: 12px; }
.count { font-weight: 400; color: #64748b; font-size: 14px; }
.data-table tbody tr.row-highlight--alert { background: #fff7ed; }
.actions { display: flex; gap: 8px; margin-top: 12px; }
</style>
