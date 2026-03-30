<template>
  <div class="bundle-settings-page">
    <header class="page-head">
      <div>
        <h1 class="page-title">도급사별 문서항목 묶음 설정</h1>
        <p class="page-sub">삼성 전용 그룹(1개) + 일반 그룹 기준으로 문서항목을 추가/제거/수정합니다.</p>
      </div>
      <div class="actions">
        <span class="pill">{{ groupKeyLabel }}</span>
      </div>
    </header>

    <BaseCard class="filter-card !p-4">
      <div class="filters">
        <div class="team-row">
          <span class="label">팀</span>
          <button
            v-for="slot in teamSlotMeta"
            :key="slot.key"
            type="button"
            class="team-btn"
            :class="{ active: teamSlot === slot.key }"
            @click="teamSlot = slot.key"
          >
            {{ slot.label }}
          </button>
        </div>

        <div v-if="teamSlot === '4'" class="contractor-row">
          <span class="label">삼성 선택</span>
          <button
            v-for="c in samsungContractors"
            :key="c"
            type="button"
            class="contractor-btn"
            :class="{ active: selectedContractors.includes(c) }"
            @click="toggleContractor(c)"
          >
            {{ c }}
          </button>
          <button type="button" class="link-reset" @click="clearSamsungSelection">일반으로</button>
        </div>
      </div>
    </BaseCard>

    <BaseCard class="filter-card !p-4">
      <div class="filters">
        <input v-model="search" type="text" class="control-input" placeholder="문서명 검색..." />
        <select v-model="cycleFilter" class="control-select">
          <option value="ALL">주기 전체</option>
          <option v-for="cycle in cycles" :key="cycle.id" :value="cycle.id">{{ cycle.name }}</option>
        </select>
      </div>
    </BaseCard>

    <BaseCard v-if="loading" class="group-card !p-4">로딩 중...</BaseCard>
    <BaseCard v-else v-for="group in groupedTypes" :key="`cycle-${group.cycleId}`" class="group-card !p-4" :title="group.title">
      <ul class="doc-list">
        <li v-for="item in group.items" :key="`row-${item.document_type_id}`" class="doc-row">
          <div class="doc-main">
            <div class="doc-name">{{ item.title }}</div>
            <div class="doc-meta">
              code: {{ item.code }} ·
              <span :class="item.is_enabled ? 'meta-active' : 'meta-disabled'">{{ item.is_enabled ? '활성' : '비활성' }}</span>
              <span v-if="item.has_override" class="meta-override">· override</span>
            </div>
          </div>

          <div class="doc-actions">
            <button
              type="button"
              class="stitch-btn-secondary btn-sm"
              @click="openEdit(item)"
            >
              수정
            </button>
            <button
              type="button"
              class="stitch-btn-secondary btn-sm btn-danger"
              :disabled="!canToggle"
              @click="toggleEnabled(item)"
            >
              {{ item.is_enabled ? "삭제" : "추가" }}
            </button>
          </div>
        </li>
        <li v-if="group.items.length === 0" class="doc-empty">항목 없음</li>
      </ul>
    </BaseCard>

    <div v-if="modalOpen" class="modal-backdrop" @click.self="closeModal">
      <BaseCard class="modal-card !w-full max-w-[640px]" :title="'문서항목 ' + (editingItem?.is_enabled ? '수정' : '추가')">
        <div class="form-grid">
          <label class="form-field">
            <span>활성 여부</span>
            <input type="checkbox" v-model="form.is_enabled" />
          </label>
          <label class="form-field">
            <span>필수 여부</span>
            <input type="checkbox" v-model="form.is_required" :disabled="!form.is_enabled" />
          </label>

          <label class="form-field">
            <span>주기</span>
            <select v-model="form.frequency" class="control-select">
              <option v-for="f in availableFrequencies" :key="f" :value="f">{{ f }}</option>
            </select>
          </label>

          <label class="form-field">
            <span>정렬 순서</span>
            <input v-model.number="form.display_order" type="number" class="control-input" min="0" />
          </label>

          <label class="form-field form-field-span-2">
            <span>시행/기한 규칙(요약)</span>
            <textarea v-model="form.due_rule_text" rows="3" class="control-textarea" />
          </label>

          <label class="form-field form-field-span-2">
            <span>비고</span>
            <textarea v-model="form.note" rows="3" class="control-textarea" />
          </label>
        </div>

        <div class="modal-actions">
          <button type="button" class="stitch-btn-secondary" @click="closeModal">취소</button>
          <button type="button" class="stitch-btn-primary" :disabled="!canSubmit" @click="saveModal">저장</button>
        </div>
      </BaseCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { api } from "@/services/api";
import { BaseCard } from "@/components/product";

type GroupKey = "SAMSUNG" | "GENERAL";
type TeamSlotKey = "1" | "2" | "3" | "4" | "5" | "6" | "gwal";

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

interface BundleRow {
  document_type_id: number;
  code: string;
  title: string;
  is_enabled: boolean;
  is_required: boolean;
  frequency: string;
  display_order: number;
  due_rule_text: string | null;
  note: string | null;
  has_override: boolean;
  base_is_enabled: boolean;
  base_is_required: boolean;
  base_frequency: string;
  base_display_order: number;
  base_due_rule_text: string | null;
  base_note: string | null;
}

const samsungContractors = ["삼성물산", "삼성E&A"];
const samsungContractorSet = new Set<string>(samsungContractors);

const teamSlotMeta: { key: TeamSlotKey; label: string }[] = [
  { key: "1", label: "1팀" },
  { key: "2", label: "2팀" },
  { key: "3", label: "3팀" },
  { key: "4", label: "4팀" },
  { key: "5", label: "5팀" },
  { key: "6", label: "6팀" },
  { key: "gwal", label: "관급" },
];

const route = useRoute();

function readGroupKeyFromRoute(): GroupKey {
  return route.query.group_key === "SAMSUNG" ? "SAMSUNG" : "GENERAL";
}

const selectedContractors = ref<string[]>(
  readGroupKeyFromRoute() === "SAMSUNG" ? [...samsungContractors] : [],
);
const teamSlot = ref<TeamSlotKey>(readGroupKeyFromRoute() === "SAMSUNG" ? "4" : "1");

const groupKey = computed<GroupKey>(() => {
  const anySamsungSelected = selectedContractors.value.some((c) => samsungContractorSet.has(c));
  return anySamsungSelected ? "SAMSUNG" : "GENERAL";
});

const groupKeyLabel = computed(() => (groupKey.value === "SAMSUNG" ? "삼성 전용 그룹" : "일반 그룹"));

const cycles = ref<SubmissionCycle[]>([]);
const documentTypes = ref<DocumentTypeItem[]>([]);
const bundleItems = ref<BundleRow[]>([]);

const search = ref("");
const cycleFilter = ref<"ALL" | number>("ALL");

const loading = ref(false);

const availableFrequencies = computed(() => {
  const set = new Set<string>();
  for (const it of bundleItems.value) set.add(it.frequency);
  return Array.from(set).sort((a, b) => a.localeCompare(b, "ko"));
});

const groupedTypes = computed(() => {
  const cycleTitleById: Record<number, string> = Object.fromEntries(
    cycles.value.map((c) => [c.id, c.name]),
  ) as Record<number, string>;
  const filtered = bundleItems.value.filter((it) => {
    if (cycleFilter.value !== "ALL") {
      const dt = documentTypes.value.find((d) => d.id === it.document_type_id);
      if (!dt || dt.default_cycle_id !== cycleFilter.value) return false;
    }
    if (!search.value.trim()) return true;
    return (it.title || "").toLowerCase().includes(search.value.trim().toLowerCase());
  });

  const groups = new Map<number, { cycleId: number; title: string; items: BundleRow[] }>();
  for (const it of filtered) {
    const dt = documentTypes.value.find((d) => d.id === it.document_type_id);
    const cycleId = dt?.default_cycle_id ?? 0;
    if (!groups.has(cycleId)) {
      groups.set(cycleId, { cycleId, title: `${cycleTitleById[cycleId] ?? `주기 ${cycleId}`}`, items: [] });
    }
    groups.get(cycleId)!.items.push(it);
  }
  const ordered = Array.from(groups.values()).sort((a, b) => a.cycleId - b.cycleId);
  for (const g of ordered) g.items.sort((a, b) => (a.display_order - b.display_order) || a.code.localeCompare(b.code, "ko"));
  return ordered;
});

const canToggle = computed(() => !loading.value && !!documentTypes.value.length);

function toggleContractor(name: string) {
  const idx = selectedContractors.value.indexOf(name);
  if (idx >= 0) selectedContractors.value.splice(idx, 1);
  else selectedContractors.value.push(name);
}

function clearSamsungSelection() {
  selectedContractors.value = [];
}

const editingItem = ref<BundleRow | null>(null);
const modalOpen = ref(false);
const form = ref({
  is_enabled: true,
  is_required: true,
  frequency: "MONTHLY",
  display_order: 0,
  due_rule_text: "",
  note: "",
});

const canSubmit = computed(() => {
  if (!editingItem.value) return false;
  if (!form.value.frequency) return false;
  if (form.value.is_enabled && form.value.is_required === false) return true;
  return true;
});

async function loadAll() {
  loading.value = true;
  try {
    const [cyclesRes, typesRes] = await Promise.all([
      api.get("/settings/document-cycles/cycles"),
      api.get("/settings/document-cycles/document-types"),
    ]);
    cycles.value = cyclesRes.data ?? [];
    documentTypes.value = (typesRes.data ?? []).filter((t: DocumentTypeItem) => t.is_active !== false);
    await loadBundleItems();
  } finally {
    loading.value = false;
  }
}

async function loadBundleItems() {
  const res = await api.get(`/settings/document-cycles/contractor-bundles/${groupKey.value}/items`);
  bundleItems.value = res.data ?? [];
}

onMounted(loadAll);

watch(
  () => groupKey.value,
  async () => {
    await loadBundleItems();
  },
);

watch(
  () => route.query.group_key,
  () => {
    // 외부에서 그룹 키를 바꿔서 진입한 경우(대시보드 버튼) 초기 상태를 동기화
    const g = readGroupKeyFromRoute();
    selectedContractors.value = g === "SAMSUNG" ? [...samsungContractors] : [];
    teamSlot.value = g === "SAMSUNG" ? "4" : "1";
  },
);

function openEdit(item: BundleRow) {
  editingItem.value = item;
  form.value = {
    is_enabled: item.is_enabled,
    is_required: item.is_required,
    frequency: item.frequency,
    display_order: item.display_order,
    due_rule_text: item.due_rule_text ?? "",
    note: item.note ?? "",
  };
  modalOpen.value = true;
}

function closeModal() {
  modalOpen.value = false;
  editingItem.value = null;
}

async function saveModal() {
  if (!editingItem.value) return;
  const payload = [
    {
      document_type_id: editingItem.value.document_type_id,
      is_enabled: form.value.is_enabled,
      is_required: form.value.is_required,
      frequency: form.value.frequency,
      display_order: form.value.display_order,
      due_rule_text: form.value.due_rule_text || null,
      note: form.value.note || null,
    },
  ];
  await api.put(`/settings/document-cycles/contractor-bundles/${groupKey.value}/items`, payload);
  await loadBundleItems();
  closeModal();
}

async function toggleEnabled(item: BundleRow) {
  // "추가"는 override를 원복(base와 동일)할 수 있도록 base 값을 우선 사용
  const nextEnabled = !item.is_enabled;
  const payload = [
    {
      document_type_id: item.document_type_id,
      is_enabled: nextEnabled,
      is_required: nextEnabled ? item.base_is_required : false,
      frequency: nextEnabled ? item.base_frequency : item.frequency,
      display_order: nextEnabled ? item.base_display_order : item.display_order,
      due_rule_text: nextEnabled ? item.base_due_rule_text : item.due_rule_text,
      note: nextEnabled ? item.base_note : item.note,
    },
  ];
  await api.put(`/settings/document-cycles/contractor-bundles/${groupKey.value}/items`, payload);
  await loadBundleItems();
}
</script>

<style scoped>
.bundle-settings-page {
  width: 100%;
}

.page-head {
  margin-bottom: 14px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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
.actions {
  display: flex;
  gap: 10px;
  align-items: center;
}
.pill {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 9999px;
  font-weight: 700;
  font-size: 13px;
  color: #0f172a;
}

.filter-card,
.group-card {
  margin-bottom: 12px;
}
.filters {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
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
.control-textarea {
  resize: vertical;
}

.team-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.contractor-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.label {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
}

.team-btn,
.contractor-btn {
  height: 36px;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  padding: 0 12px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.team-btn.active,
.contractor-btn.active {
  background: #1d4ed8;
  border-color: #1d4ed8;
  color: #fff;
}
.link-reset {
  border: 0;
  background: transparent;
  color: #1d4ed8;
  cursor: pointer;
  padding: 0 4px;
  font-weight: 700;
  font-size: 12px;
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
  gap: 12px;
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
.meta-active {
  color: #166534;
  font-weight: 700;
}
.meta-disabled {
  color: #9a3412;
  font-weight: 700;
}
.meta-override {
  color: #0f172a;
  font-weight: 700;
}
.doc-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
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
  font-weight: 700;
}
.form-field input[type="checkbox"] {
  width: 20px;
  height: 20px;
}
.form-field-span-2 {
  grid-column: 1 / -1;
}
.control-textarea {
  min-height: 90px;
}
.modal-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>

