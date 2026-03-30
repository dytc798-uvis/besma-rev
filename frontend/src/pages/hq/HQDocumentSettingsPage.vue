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
