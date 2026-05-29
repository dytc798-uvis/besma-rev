<template>
  <div class="fe-page">
    <div class="page-head">
      <div>
        <h1 class="page-title">기능인 인사고과 · 제재</h1>
        <p class="page-sub">
          마감일: <strong>{{ period?.deadline_date || "—" }}</strong>
          <span v-if="period?.is_closed" class="badge closed">마감됨</span>
          <span v-else class="badge open">진행 중</span>
        </p>
      </div>
      <button class="stitch-btn-secondary" type="button" @click="load">새로고침</button>
    </div>

    <section v-if="selectedWorker" class="panel sanction-form">
      <h2>{{ selectedWorker.name }} — 위반·제재 등록</h2>
      <label>
        위반 항목
        <select v-model="form.violation_code">
          <optgroup v-for="group in groupedViolations" :key="group.category" :label="group.label">
            <option v-for="item in group.items" :key="item.code" :value="item.code">{{ item.label }}</option>
          </optgroup>
        </select>
      </label>
      <label>
        비고
        <textarea v-model="form.note" rows="2" placeholder="위반 상황 (선택)" />
      </label>
      <div class="actions">
        <button class="stitch-btn-secondary" type="button" @click="closeForm">취소</button>
        <button
          class="stitch-btn-primary"
          type="button"
          :disabled="!form.violation_code || saving || period?.is_closed"
          @click="submitSanction"
        >
          {{ saving ? "등록 중..." : "제재 등록" }}
        </button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </section>

    <section v-if="historyWorker" class="panel history-panel">
      <div class="history-head">
        <h2>{{ historyWorker.name }} — 이력</h2>
        <button class="link-btn" type="button" @click="historyWorker = null">닫기</button>
      </div>
      <p v-if="!historyData?.history_visible" class="warn">{{ historyData?.message }}</p>
      <ul v-else class="history-list">
        <li v-for="s in allHistorySanctions" :key="`${s.id}-h`">
          <span v-if="s.from_prior_period" class="tag">이전</span>
          {{ s.violation_label }} → {{ s.sanction_result_label }} ({{ s.strike_number }}차)
          <span class="meta">{{ formatDate(s.created_at) }}</span>
        </li>
        <li v-if="!allHistorySanctions.length">제재 이력 없음</li>
      </ul>
      <div class="mileage-box">
        <h3>마일리지 (운영 준비)</h3>
        <p>{{ historyData?.mileage?.message }}</p>
        <p class="meta">적립 예정 포인트: {{ historyData?.mileage?.points ?? 0 }}</p>
      </div>
    </section>

    <section class="panel">
      <h2>현장 근로자 ({{ workers.length }}명)</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th>번호</th>
            <th>성명</th>
            <th>제재 상태</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="w in workers" :key="w.id">
            <td>{{ w.row_no }}</td>
            <td>{{ w.name }}</td>
            <td>
              <span :class="['status-pill', statusClass(w.sanction_status)]">{{ w.sanction_status_label }}</span>
            </td>
            <td class="actions-cell">
              <button class="link-btn" type="button" @click="openHistory(w)">이력</button>
              <button
                class="link-btn"
                type="button"
                :disabled="period?.is_closed || w.is_permanently_expelled"
                @click="openSanction(w)"
              >
                제재
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "@/services/api";

interface Period {
  id: number;
  deadline_date: string;
  is_closed: boolean;
}

interface ViolationItem {
  code: string;
  category: string;
  category_label: string;
  label: string;
}

interface Worker {
  id: number;
  row_no: number;
  name: string;
  sanction_status: string;
  sanction_status_label: string;
  is_permanently_expelled: boolean;
  history_visible: boolean;
}

interface SanctionRow {
  id: number;
  violation_label: string;
  sanction_result_label: string;
  strike_number: number;
  created_at: string;
  from_prior_period?: boolean;
}

const period = ref<Period | null>(null);
const workers = ref<Worker[]>([]);
const violations = ref<ViolationItem[]>([]);
const selectedWorker = ref<Worker | null>(null);
const historyWorker = ref<Worker | null>(null);
const historyData = ref<{
  history_visible: boolean;
  message?: string;
  sanctions: SanctionRow[];
  prior_sanctions: SanctionRow[];
  mileage: { message?: string; points?: number };
} | null>(null);
const saving = ref(false);
const error = ref("");
const form = reactive({ violation_code: "", note: "" });

const groupedViolations = computed(() => {
  const map = new Map<string, { category: string; label: string; items: ViolationItem[] }>();
  for (const item of violations.value) {
    if (!map.has(item.category)) {
      map.set(item.category, { category: item.category, label: item.category_label, items: [] });
    }
    map.get(item.category)!.items.push(item);
  }
  return Array.from(map.values());
});

const allHistorySanctions = computed(() => {
  if (!historyData.value?.history_visible) return [];
  return [...(historyData.value.prior_sanctions || []), ...(historyData.value.sanctions || [])];
});

function statusClass(status: string) {
  if (status.includes("EXPULSION") || status.includes("BAN")) return "danger";
  if (status.includes("WARNING") || status.includes("TRAINING")) return "warn";
  return "normal";
}

function formatDate(v: string) {
  try {
    return new Date(v).toLocaleString("ko-KR");
  } catch {
    return v;
  }
}

async function loadCatalog() {
  const res = await api.get("/functional-eval/violation-catalog");
  violations.value = res.data.items || [];
  if (violations.value.length && !form.violation_code) {
    form.violation_code = violations.value[0].code;
  }
}

async function load() {
  error.value = "";
  const res = await api.get("/functional-eval/my-site/workers");
  period.value = res.data.period;
  workers.value = res.data.items || [];
}

async function openHistory(worker: Worker) {
  historyWorker.value = worker;
  selectedWorker.value = null;
  const res = await api.get(`/functional-eval/workers/${worker.id}/history`);
  historyData.value = res.data;
}

function openSanction(worker: Worker) {
  selectedWorker.value = worker;
  historyWorker.value = null;
  form.note = "";
}

function closeForm() {
  selectedWorker.value = null;
}

async function submitSanction() {
  if (!selectedWorker.value) return;
  saving.value = true;
  error.value = "";
  try {
    await api.post("/functional-eval/sanctions", {
      worker_id: selectedWorker.value.id,
      violation_code: form.violation_code,
      note: form.note || null,
    });
    selectedWorker.value = null;
    await load();
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof msg === "string" ? msg : "제재 등록에 실패했습니다.";
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await Promise.all([loadCatalog(), load()]);
});
</script>

<style scoped>
.fe-page { display: flex; flex-direction: column; gap: 16px; }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; }
.page-title { margin: 0; font-size: 1.4rem; }
.page-sub { margin: 6px 0 0; color: #64748b; }
.badge { margin-left: 8px; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.badge.open { background: #dcfce7; color: #166534; }
.badge.closed { background: #fee2e2; color: #991b1b; }
.panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.sanction-form label { display: block; margin-top: 12px; }
.sanction-form select, .sanction-form textarea { width: 100%; margin-top: 4px; }
.actions { display: flex; gap: 8px; margin-top: 12px; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; }
.actions-cell { display: flex; gap: 8px; }
.status-pill { padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.status-pill.danger { background: #fee2e2; color: #991b1b; }
.status-pill.warn { background: #fef3c7; color: #92400e; }
.status-pill.normal { background: #f1f5f9; color: #475569; }
.error { color: #b91c1c; margin-top: 8px; }
.history-list { padding-left: 18px; font-size: 14px; }
.history-head { display: flex; justify-content: space-between; align-items: center; }
.mileage-box { margin-top: 16px; padding: 12px; background: #f1f5f9; border-radius: 8px; }
.mileage-box h3 { margin: 0 0 8px; font-size: 14px; }
.tag { font-size: 11px; background: #e2e8f0; padding: 1px 6px; border-radius: 4px; margin-right: 4px; }
.warn { color: #991b1b; }
.meta { color: #64748b; font-size: 12px; margin-left: 6px; }
</style>
