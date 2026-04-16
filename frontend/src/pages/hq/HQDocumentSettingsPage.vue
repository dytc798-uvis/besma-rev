<template>
  <div class="doc-settings-page">
    <header class="page-head">
      <div>
        <h1 class="page-title">안전문서 설정</h1>
        <p class="page-sub">문서 항목 추가/수정/삭제와 주기 변경을 관리합니다.</p>
      </div>
      <button type="button" class="stitch-btn-primary" @click="openCreate">+ 서류 추가</button>
    </header>

    <BaseCard v-if="canUploadSawonList" class="filter-card !p-4" title="사원리스트 반영">
      <p class="sawon-hint">
        본사 사원리스트(.xls / .xlsx)를 업로드하면 직원 마스터(DB)에 반영됩니다. 파일 형식 때문에 읽기에 실패하면 서버에서 변환 후 다시 적용을 시도합니다.
      </p>
      <div class="sawon-upload-row">
        <input
          ref="sawonFileInput"
          type="file"
          accept=".xls,.xlsx,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          class="control-input sawon-file-input"
          @change="onSawonFileChange"
        />
        <button
          type="button"
          class="stitch-btn-primary"
          :disabled="!sawonSelectedFile || sawonUploading"
          @click="uploadSawonList"
        >
          {{ sawonUploading ? "업로드 중…" : "업로드 및 반영" }}
        </button>
      </div>
      <pre v-if="sawonFeedback" class="sawon-feedback">{{ sawonFeedback }}</pre>
    </BaseCard>

    <BaseCard class="filter-card !p-4">
      <div class="filters">
        <input v-model="search" type="text" class="control-input" placeholder="문서 코드 검색..." />
        <select v-model="cycleFilter" class="control-select">
          <option value="ALL">주기 전체</option>
          <option v-for="cycle in cycles" :key="cycle.id" :value="cycle.id">{{ cycle.name }}</option>
        </select>
      </div>
    </BaseCard>

    <BaseCard class="group-card !p-4" title="동적 메뉴 설정 (방침 및 목표 아래)">
      <p class="page-sub" style="margin:0 0 10px">
        동적 메뉴 추가/수정/삭제 후, 아래 <strong>전체 메뉴 순서 설정</strong>에서 대시보드를 제외한 전체 메뉴 순서를 확정하세요.
      </p>
      <div class="doc-actions" style="margin-bottom:10px">
        <button type="button" class="stitch-btn-primary btn-sm" @click="openDynamicMenuCreate">+ 메뉴 추가</button>
        <button type="button" class="stitch-btn-secondary btn-sm" @click="saveDynamicMenuOrder">동적메뉴 내부 순서 저장</button>
      </div>
      <ul class="doc-list">
        <li
          v-for="(menu, idx) in dynamicMenus"
          :key="`dyn-${menu.id}`"
          class="doc-row"
          draggable="true"
          @dragstart="onDynamicMenuDragStart(idx)"
          @dragover.prevent
          @drop="onDynamicMenuDrop(idx)"
        >
          <div class="doc-main">
            <div class="doc-name">{{ idx + 1 }}. {{ menu.title }}</div>
            <div class="doc-meta">{{ menu.menu_type }} / {{ menu.target_ui_type }} / {{ menu.is_active ? "활성" : "비활성" }}</div>
          </div>
          <div class="doc-actions">
            <button type="button" class="stitch-btn-secondary btn-sm" @click="openDynamicMenuEdit(menu)">수정</button>
            <button type="button" class="stitch-btn-secondary btn-sm btn-danger" @click="removeDynamicMenu(menu.id)">삭제</button>
          </div>
        </li>
      </ul>
    </BaseCard>

    <BaseCard class="group-card !p-4" title="전체 메뉴 순서 설정 (대시보드 제외)">
      <div class="filters" style="margin-bottom:10px">
        <select v-model="menuOrderUiType" class="control-select" @change="reloadMenuOrderItems">
          <option value="SITE">SITE 메뉴</option>
          <option value="HQ_SAFE">HQ_SAFE 메뉴</option>
        </select>
        <button type="button" class="stitch-btn-secondary btn-sm" @click="reloadMenuOrderItems">목록 새로고침</button>
        <button type="button" class="stitch-btn-primary btn-sm" @click="saveSidebarMenuOrder">메뉴 순서 저장</button>
      </div>
      <ul class="doc-list">
        <li
          v-for="(item, idx) in menuOrderItems"
          :key="`menu-order-${item.key}`"
          class="doc-row"
          draggable="true"
          @dragstart="onMenuOrderDragStart(idx)"
          @dragover.prevent
          @drop="onMenuOrderDrop(idx)"
        >
          <div class="doc-main">
            <div class="doc-name">{{ idx + 1 }}. {{ item.label }}</div>
            <div class="doc-meta">{{ item.kind === "dynamic" ? "동적 메뉴" : "고정 메뉴" }} / key: {{ item.key }}</div>
          </div>
        </li>
      </ul>
    </BaseCard>

    <BaseCard
      v-for="group in groupedTypes"
      :key="`group-${group.cycleId}`"
      class="group-card !p-4"
      :title="group.title"
    >
      <ul class="doc-list">
        <li v-for="item in group.items" :key="item.id" class="doc-row">
          <div class="doc-main">
            <div class="doc-name">{{ item.code }}</div>
          </div>
          <div class="doc-actions">
            <button type="button" class="stitch-btn-secondary btn-sm" @click="openEdit(item)">수정</button>
            <button type="button" class="stitch-btn-secondary btn-sm btn-danger" @click="removeItem(item)">
              삭제
            </button>
          </div>
        </li>
        <li v-if="group.items.length === 0" class="doc-empty">항목 없음</li>
      </ul>
    </BaseCard>

    <div v-if="modalOpen" class="modal-backdrop" @click.self="closeModal">
      <BaseCard class="modal-card !w-full max-w-[560px]" :title="editingId ? '문서 항목 수정' : '문서 항목 추가'">
        <div class="form-grid">
          <label class="form-field">
            <span>문서 코드</span>
            <input v-model="form.code" class="control-input" :disabled="!!editingId" placeholder="예: CUSTOM_DOC" />
          </label>
          <label class="form-field">
            <span>문서명</span>
            <input v-model="form.name" class="control-input" placeholder="문서명" />
          </label>
          <label class="form-field">
            <span>주기</span>
            <select v-model.number="form.default_cycle_id" class="control-select">
              <option v-for="cycle in cycles" :key="`cycle-opt-${cycle.id}`" :value="cycle.id">
                {{ cycle.name }}
              </option>
            </select>
          </label>
          <label class="form-field">
            <span>정렬 순서</span>
            <input v-model.number="form.sort_order" type="number" class="control-input" min="0" />
          </label>
          <label class="form-field form-field-span-2">
            <span>설명</span>
            <textarea v-model="form.description" rows="3" class="control-textarea" />
          </label>
        </div>
        <div class="modal-actions">
          <button type="button" class="stitch-btn-secondary" @click="closeModal">취소</button>
          <button type="button" class="stitch-btn-primary" :disabled="!canSubmit" @click="submitForm">
            저장
          </button>
        </div>
      </BaseCard>
    </div>

    <div v-if="dynamicMenuModalOpen" class="modal-backdrop" @click.self="closeDynamicMenuModal">
      <BaseCard class="modal-card !w-full max-w-[640px]" :title="dynamicMenuEditingId ? '동적 메뉴 수정' : '동적 메뉴 추가'">
        <div class="form-grid">
          <label class="form-field">
            <span>메뉴명</span>
            <input v-model="dynamicMenuForm.title" class="control-input" placeholder="예: 안전 캠페인 게시판" />
          </label>
          <label class="form-field">
            <span>메뉴 타입</span>
            <select v-model="dynamicMenuForm.menu_type" class="control-select">
              <option value="BOARD">게시판형</option>
              <option value="TABLE">표형</option>
            </select>
          </label>
          <label class="form-field">
            <span>노출 대상</span>
            <select v-model="dynamicMenuForm.target_ui_type" class="control-select">
              <option value="SITE">SITE</option>
              <option value="HQ_SAFE">HQ_SAFE</option>
              <option value="BOTH">BOTH</option>
            </select>
          </label>
          <label class="form-field">
            <span>활성 여부</span>
            <select v-model="dynamicMenuForm.is_active" class="control-select">
              <option :value="true">활성</option>
              <option :value="false">비활성</option>
            </select>
          </label>
          <label v-if="dynamicMenuForm.menu_type === 'BOARD'" class="form-field form-field-span-2">
            <span>게시판 옵션(JSON)</span>
            <textarea v-model="dynamicMenuConfigText" rows="4" class="control-textarea" placeholder='{"allow_comments": true}' />
          </label>
          <label v-else class="form-field form-field-span-2">
            <span>표 컬럼(한 줄에 key|label)</span>
            <textarea
              v-model="dynamicMenuColumnsText"
              rows="5"
              class="control-textarea"
              placeholder="name|이름&#10;date|일자&#10;status|상태"
            />
          </label>
        </div>
        <div class="modal-actions">
          <button type="button" class="stitch-btn-secondary" @click="closeDynamicMenuModal">취소</button>
          <button type="button" class="stitch-btn-primary" @click="submitDynamicMenu">저장</button>
        </div>
      </BaseCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";
import { BaseCard } from "@/components/product";
import { useAuthStore } from "@/stores/auth";

interface SubmissionCycle {
  id: number;
  code: string;
  name: string;
  sort_order: number;
  is_active: boolean;
  is_auto_generatable: boolean;
}

interface DocumentTypeItem {
  id: number;
  code: string;
  name: string;
  description: string | null;
  sort_order: number;
  is_active: boolean;
  default_cycle_id: number;
}

interface DynamicMenuItem {
  id: number;
  slug: string;
  title: string;
  menu_type: "BOARD" | "TABLE";
  target_ui_type: "SITE" | "HQ_SAFE" | "BOTH";
  sort_order: number;
  is_active: boolean;
  custom_config: Record<string, unknown>;
}
interface MenuOrderItem {
  key: string;
  label: string;
  kind: "fixed" | "dynamic";
}

const auth = useAuthStore();

const cycles = ref<SubmissionCycle[]>([]);
const items = ref<DocumentTypeItem[]>([]);
const search = ref("");
const cycleFilter = ref<"ALL" | number>("ALL");

const sawonFileInput = ref<HTMLInputElement | null>(null);
const sawonSelectedFile = ref<File | null>(null);
const sawonUploading = ref(false);
const sawonFeedback = ref("");

const canUploadSawonList = computed(() => {
  const r = auth.user?.role;
  return r === "HQ_SAFE" || r === "HQ_SAFE_ADMIN" || r === "SUPER_ADMIN";
});

const modalOpen = ref(false);
const editingId = ref<number | null>(null);
const form = ref({
  code: "",
  name: "",
  description: "",
  sort_order: 0,
  default_cycle_id: 0,
});
const dynamicMenus = ref<DynamicMenuItem[]>([]);
const dynamicMenuDragIndex = ref<number | null>(null);
const dynamicMenuModalOpen = ref(false);
const dynamicMenuEditingId = ref<number | null>(null);
const dynamicMenuForm = ref({
  title: "",
  menu_type: "BOARD" as "BOARD" | "TABLE",
  target_ui_type: "SITE" as "SITE" | "HQ_SAFE" | "BOTH",
  is_active: true,
});
const dynamicMenuConfigText = ref('{"allow_comments": true}');
const dynamicMenuColumnsText = ref("name|이름\nnote|내용");
const menuOrderUiType = ref<"SITE" | "HQ_SAFE">("HQ_SAFE");
const menuOrderItems = ref<MenuOrderItem[]>([]);
const menuOrderDragIndex = ref<number | null>(null);
const FIXED_MENU_LABELS: Record<"SITE" | "HQ_SAFE", Array<{ key: string; label: string }>> = {
  SITE: [
    { key: "notices", label: "공지사항" },
    { key: "safety-policy-goals", label: "안전보건 방침 및 목표" },
    { key: "safety-education", label: "안전 교육" },
    { key: "safety-inspections", label: "안전 점검" },
    { key: "nonconformities", label: "부적합사항" },
    { key: "worker-voice", label: "근로자의견청취" },
    { key: "mobile", label: "일일안전회의(일일위험성평가)" },
    { key: "mobile-site-search", label: "현장 검색" },
    { key: "document-explorer", label: "문서 탐색" },
    { key: "risk-library", label: "위험성평가 DB 조회" },
    { key: "documents", label: "내 현장 문서" },
    { key: "communications", label: "소통자료" },
    { key: "opinions", label: "운영 아이디어 제안" },
    { key: "info", label: "설정" },
    { key: "user-guide", label: "사용설명서" },
  ],
  HQ_SAFE: [
    { key: "tbm-monitor", label: "TBM 모니터" },
    { key: "risk-library", label: "위험성평가 DB 조회" },
    { key: "site-search", label: "현장 검색" },
    { key: "document-explorer", label: "문서 탐색" },
    { key: "periodic-monitoring", label: "주기 기반 문서 모니터링" },
    { key: "documents", label: "문서 취합 현황" },
    { key: "approvals-inbox", label: "결재함(공사중)" },
    { key: "approvals-history", label: "승인/반려 이력" },
    { key: "opinions", label: "운영 아이디어 제안" },
    { key: "notices", label: "공지사항" },
    { key: "safety-policy-goals", label: "안전보건 방침 및 목표" },
    { key: "safety-education", label: "안전 교육" },
    { key: "safety-inspections", label: "안전 점검" },
    { key: "nonconformities", label: "부적합사항" },
    { key: "worker-voice", label: "근로자의견청취" },
    { key: "sites", label: "현장 관리" },
    { key: "users", label: "사용자 관리" },
    { key: "settings", label: "안전문서 설정관리" },
    { key: "user-guide", label: "사용설명서" },
  ],
};

const cycleNameById = computed(() =>
  Object.fromEntries(cycles.value.map((cycle) => [cycle.id, cycle.name])) as Record<number, string>,
);

const filteredItems = computed(() =>
  items.value.filter((item) => {
    if (cycleFilter.value !== "ALL" && item.default_cycle_id !== cycleFilter.value) return false;
    if (!search.value.trim()) return true;
    const q = search.value.trim().toLowerCase();
    return `${item.code} ${item.name}`.toLowerCase().includes(q);
  }),
);

const groupedTypes = computed(() => {
  const groups = new Map<number, { cycleId: number; title: string; items: DocumentTypeItem[] }>();
  for (const item of filteredItems.value) {
    const cycleTitle = cycleNameById.value[item.default_cycle_id] ?? `주기 ${item.default_cycle_id}`;
    const title = `${cycleTitle}`;
    if (!groups.has(item.default_cycle_id)) {
      groups.set(item.default_cycle_id, {
        cycleId: item.default_cycle_id,
        title,
        items: [],
      });
    }
    groups.get(item.default_cycle_id)!.items.push(item);
  }
  const ordered = Array.from(groups.values()).sort((a, b) => a.cycleId - b.cycleId);
  for (const group of ordered) {
    group.items.sort((a, b) => a.sort_order - b.sort_order || a.code.localeCompare(b.code, "ko"));
  }
  return ordered;
});

const canSubmit = computed(() => !!form.value.code.trim() && !!form.value.name.trim() && !!form.value.default_cycle_id);

async function load() {
  const [cyclesRes, typesRes] = await Promise.all([
    api.get("/settings/document-cycles/cycles"),
    api.get("/settings/document-cycles/document-types"),
  ]);
  cycles.value = cyclesRes.data ?? [];
  items.value = (typesRes.data ?? []).filter((item: DocumentTypeItem) => item.is_active !== false);
  if (!form.value.default_cycle_id && cycles.value.length > 0) {
    form.value.default_cycle_id = cycles.value[0].id;
  }
  const menuRes = await api.get("/settings/document-cycles/dynamic-menus");
  dynamicMenus.value = menuRes.data?.items ?? [];
  await reloadMenuOrderItems();
}

function openCreate() {
  editingId.value = null;
  form.value = {
    code: "",
    name: "",
    description: "",
    sort_order: items.value.length + 1,
    default_cycle_id: cycles.value[0]?.id ?? 0,
  };
  modalOpen.value = true;
}

function openEdit(item: DocumentTypeItem) {
  editingId.value = item.id;
  form.value = {
    code: item.code,
    name: item.name,
    description: item.description ?? "",
    sort_order: item.sort_order ?? 0,
    default_cycle_id: item.default_cycle_id,
  };
  modalOpen.value = true;
}

function closeModal() {
  modalOpen.value = false;
}

async function submitForm() {
  if (!canSubmit.value) return;
  const payload = {
    code: form.value.code.trim().toUpperCase(),
    name: form.value.name.trim(),
    description: form.value.description.trim() || null,
    sort_order: Number(form.value.sort_order) || 0,
    default_cycle_id: form.value.default_cycle_id,
    generation_rule: null,
    generation_value: null,
    due_offset_days: null,
    is_required_default: true,
    is_active: true,
  };
  if (editingId.value) {
    await api.put(`/settings/document-cycles/document-types/${editingId.value}`, payload);
  } else {
    await api.post("/settings/document-cycles/document-types", payload);
  }
  closeModal();
  await load();
}

async function removeItem(item: DocumentTypeItem) {
  if (!window.confirm(`'${item.code}' 항목을 삭제하시겠습니까?`)) return;
  await api.delete(`/settings/document-cycles/document-types/${item.id}`);
  await load();
}

function onDynamicMenuDragStart(index: number) {
  dynamicMenuDragIndex.value = index;
}

function onDynamicMenuDrop(index: number) {
  if (dynamicMenuDragIndex.value === null || dynamicMenuDragIndex.value === index) return;
  const copied = [...dynamicMenus.value];
  const [moved] = copied.splice(dynamicMenuDragIndex.value, 1);
  copied.splice(index, 0, moved);
  dynamicMenus.value = copied;
  dynamicMenuDragIndex.value = null;
}

async function saveDynamicMenuOrder() {
  await api.post("/settings/document-cycles/dynamic-menus/reorder", {
    items: dynamicMenus.value.map((m, idx) => ({ id: m.id, sort_order: idx + 1 })),
  });
  await load();
}

function onMenuOrderDragStart(index: number) {
  menuOrderDragIndex.value = index;
}

function onMenuOrderDrop(index: number) {
  if (menuOrderDragIndex.value === null || menuOrderDragIndex.value === index) return;
  const copied = [...menuOrderItems.value];
  const [moved] = copied.splice(menuOrderDragIndex.value, 1);
  copied.splice(index, 0, moved);
  menuOrderItems.value = copied;
  menuOrderDragIndex.value = null;
}

async function reloadMenuOrderItems() {
  const uiType = menuOrderUiType.value;
  const fixed = FIXED_MENU_LABELS[uiType].map((item) => ({ ...item, kind: "fixed" as const }));
  const dynamic = dynamicMenus.value
    .filter((menu) => menu.target_ui_type === "BOTH" || menu.target_ui_type === uiType)
    .map((menu) => ({
      key: `dynamic:${menu.id}`,
      label: menu.title,
      kind: "dynamic" as const,
    }));
  const defaults = [...fixed, ...dynamic];
  try {
    const res = await api.get(`/settings/document-cycles/menu-orders/${uiType}`);
    const orderedKeys = Array.isArray(res.data?.ordered_keys) ? (res.data.ordered_keys as string[]) : [];
    const indexMap = Object.fromEntries(orderedKeys.map((key, idx) => [key, idx]));
    menuOrderItems.value = [...defaults].sort((a, b) => {
      const ai = indexMap[a.key];
      const bi = indexMap[b.key];
      if (ai === undefined && bi === undefined) return 0;
      if (ai === undefined) return 1;
      if (bi === undefined) return -1;
      return ai - bi;
    });
  } catch {
    menuOrderItems.value = defaults;
  }
}

async function saveSidebarMenuOrder() {
  const uiType = menuOrderUiType.value;
  await api.put(`/settings/document-cycles/menu-orders/${uiType}`, {
    ordered_keys: menuOrderItems.value.map((item) => item.key),
  });
  window.dispatchEvent(new CustomEvent("besma-menu-order-updated", { detail: { uiType } }));
}

function openDynamicMenuCreate() {
  dynamicMenuEditingId.value = null;
  dynamicMenuForm.value = { title: "", menu_type: "BOARD", target_ui_type: "SITE", is_active: true };
  dynamicMenuConfigText.value = '{"allow_comments": true}';
  dynamicMenuColumnsText.value = "name|이름\nnote|내용";
  dynamicMenuModalOpen.value = true;
}

function openDynamicMenuEdit(menu: DynamicMenuItem) {
  dynamicMenuEditingId.value = menu.id;
  dynamicMenuForm.value = {
    title: menu.title,
    menu_type: menu.menu_type,
    target_ui_type: menu.target_ui_type,
    is_active: menu.is_active,
  };
  dynamicMenuConfigText.value = JSON.stringify(menu.custom_config || {}, null, 2);
  const cols = Array.isArray((menu.custom_config as any)?.columns) ? (menu.custom_config as any).columns : [];
  dynamicMenuColumnsText.value = cols.map((c: any) => `${c.key}|${c.label}`).join("\n") || "name|이름\nnote|내용";
  dynamicMenuModalOpen.value = true;
}

function closeDynamicMenuModal() {
  dynamicMenuModalOpen.value = false;
}

function buildDynamicMenuCustomConfig() {
  if (dynamicMenuForm.value.menu_type === "BOARD") {
    try {
      const obj = JSON.parse(dynamicMenuConfigText.value || "{}");
      return typeof obj === "object" && obj ? obj : {};
    } catch {
      return {};
    }
  }
  const lines = dynamicMenuColumnsText.value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const columns = lines.map((line) => {
    const [key, label] = line.split("|").map((v) => (v || "").trim());
    return { key: key || "col", label: label || key || "컬럼" };
  });
  return { columns };
}

async function submitDynamicMenu() {
  const title = dynamicMenuForm.value.title.trim();
  if (!title) return;
  const payload = {
    title,
    menu_type: dynamicMenuForm.value.menu_type,
    target_ui_type: dynamicMenuForm.value.target_ui_type,
    is_active: dynamicMenuForm.value.is_active,
    custom_config: buildDynamicMenuCustomConfig(),
  };
  if (dynamicMenuEditingId.value) {
    await api.put(`/settings/document-cycles/dynamic-menus/${dynamicMenuEditingId.value}`, payload);
  } else {
    await api.post("/settings/document-cycles/dynamic-menus", payload);
  }
  dynamicMenuModalOpen.value = false;
  await load();
}

async function removeDynamicMenu(menuId: number) {
  if (!window.confirm("이 동적 메뉴를 삭제하시겠습니까?")) return;
  await api.delete(`/settings/document-cycles/dynamic-menus/${menuId}`);
  await load();
}

function onSawonFileChange(ev: Event) {
  const el = ev.target as HTMLInputElement;
  sawonSelectedFile.value = el.files?.[0] ?? null;
  sawonFeedback.value = "";
}

async function uploadSawonList() {
  if (!sawonSelectedFile.value) return;
  sawonUploading.value = true;
  sawonFeedback.value = "";
  try {
    const fd = new FormData();
    fd.append("file", sawonSelectedFile.value);
    const res = await api.post("/workers/import/sawon-list", fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    const d = res.data as {
      total_rows: number;
      created_rows: number;
      updated_rows: number;
      failed_rows: number;
      warning_summary?: string | null;
      ingestion?: { conversion_applied?: string; imported_employee_rows?: number };
    };
    const lines = [
      `처리 완료: 총 ${d.total_rows}행 (반영 대상 행 ${d.ingestion?.imported_employee_rows ?? "—"})`,
      `신규 ${d.created_rows}, 수정 ${d.updated_rows}, 실패 ${d.failed_rows}`,
      d.warning_summary ? `경고: ${d.warning_summary}` : "",
      d.ingestion?.conversion_applied ? `적용된 변환: ${d.ingestion.conversion_applied}` : "",
    ].filter(Boolean);
    sawonFeedback.value = lines.join("\n");
  } catch (e: unknown) {
    const ax = e as { response?: { data?: { detail?: string; ingestion?: unknown } } };
    const detail = ax.response?.data?.detail ?? "업로드에 실패했습니다.";
    const ing = ax.response?.data?.ingestion;
    sawonFeedback.value =
      ing !== undefined && ing !== null
        ? `${detail}\n${JSON.stringify(ing, null, 2)}`
        : detail;
  } finally {
    sawonUploading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.page-head {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.page-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
}

.page-sub {
  margin: 6px 0 0;
  font-size: 14px;
  color: #64748b;
}

.filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.control-input,
.control-select,
.control-textarea {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  background: #fff;
  width: 100%;
  box-sizing: border-box;
}

.filter-card,
.group-card {
  margin-bottom: 12px;
}

.sawon-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}

.sawon-upload-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.sawon-file-input {
  flex: 1 1 220px;
  max-width: 100%;
}

.sawon-feedback {
  margin: 12px 0 0;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  color: #0f172a;
}

.doc-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 8px;
}

.doc-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.doc-main {
  min-width: 0;
}

.doc-name {
  font-weight: 700;
  color: #0f172a;
}

.doc-meta {
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}

.doc-actions {
  display: flex;
  gap: 8px;
}

.btn-sm {
  padding: 6px 10px;
  font-size: 12px;
}

.btn-danger {
  color: #b91c1c;
}

.doc-empty {
  color: #64748b;
  font-size: 13px;
  padding: 8px 4px;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal-card {
  padding: 20px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 12px;
}

.form-field {
  display: grid;
  gap: 6px;
}

.form-field span {
  font-size: 12px;
  color: #64748b;
}

.form-field-span-2 {
  grid-column: 1 / -1;
}

.modal-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
