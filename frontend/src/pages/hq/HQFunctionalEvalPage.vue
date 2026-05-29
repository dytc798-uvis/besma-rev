<template>
  <div class="fe-hq-page">
    <div class="page-head">
      <div>
        <h1 class="page-title">기능인제 인사고과 · 제재 관리</h1>
        <p class="page-sub">일용직 명부 DIFF 반영, 마감일, 제재·마일리지(준비) 조회</p>
      </div>
      <button class="stitch-btn-secondary" type="button" @click="load">새로고침</button>
    </div>

    <section class="panel">
      <h2>평가 회차</h2>
      <div class="row">
        <label>
          마감일
          <input v-model="deadlineInput" type="date" />
        </label>
        <button class="stitch-btn-primary" type="button" :disabled="!period" @click="saveDeadline">마감일 저장</button>
        <span v-if="period?.is_closed" class="badge closed">마감됨</span>
        <span v-else class="badge open">진행 중</span>
      </div>
    </section>

    <section class="panel">
      <h2>일용직 명부 (xlsx)</h2>
      <p class="panel-sub">먼저 DIFF를 확인한 뒤 반영합니다. 기존 제재 이력은 주민번호 기준으로 유지됩니다.</p>
      <div class="row import-row">
        <input ref="fileInput" type="file" accept=".xlsx,.xls" @change="onFileChange" />
        <button class="stitch-btn-secondary" type="button" :disabled="!rosterFile || diffing" @click="runDiff">
          {{ diffing ? "DIFF 계산 중..." : "DIFF 미리보기" }}
        </button>
        <button class="stitch-btn-primary" type="button" :disabled="!rosterFile || applying" @click="applyRoster">
          {{ applying ? "반영 중..." : "DIFF 반영" }}
        </button>
        <button class="stitch-btn-secondary" type="button" :disabled="!period?.is_closed" @click="downloadExport">
          마감 후 엑셀
        </button>
      </div>
      <div v-if="diffResult" class="diff-summary">
        <span>신규 {{ diffResult.new_count }}</span>
        <span>변경 {{ diffResult.updated_count }}</span>
        <span>동일 {{ diffResult.unchanged_count }}</span>
        <span>제외 {{ diffResult.removed_count }}</span>
        <span class="meta">(파싱 {{ diffResult.parsed_rows }}명)</span>
      </div>
      <table v-if="diffResult?.items?.length" class="data-table compact">
        <thead>
          <tr>
            <th>유형</th>
            <th>현장</th>
            <th>성명</th>
            <th>변경</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in diffPreviewItems" :key="idx">
            <td><span :class="['diff-type', item.type]">{{ diffTypeLabel(item.type) }}</span></td>
            <td>{{ item.site_code }}</td>
            <td>{{ item.name }}</td>
            <td>{{ formatChanges(item.changes) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="applyResult" class="meta success">{{ applyResult }}</p>
    </section>

    <section class="panel">
      <div class="toolbar">
        <label>
          정렬
          <select v-model="sortBy" @change="load">
            <option value="site_code">현장코드</option>
            <option value="name">성명</option>
            <option value="sanction_status">제재상태</option>
            <option value="sanction_count">제재횟수</option>
          </select>
        </label>
        <label>
          방향
          <select v-model="sortDir" @change="load">
            <option value="asc">오름차순</option>
            <option value="desc">내림차순</option>
          </select>
        </label>
        <label class="checkbox-label">
          <input v-model="includeInactive" type="checkbox" @change="load" />
          명부 제외 포함
        </label>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>현장</th>
            <th>성명</th>
            <th>명부</th>
            <th>제재상태</th>
            <th>이력</th>
            <th>마일리지</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.worker.id">
            <td>{{ item.worker.site_code }}</td>
            <td>
              <button class="link-btn" type="button" @click="openHistory(item.worker.id)">{{ item.worker.name }}</button>
            </td>
            <td>{{ item.worker.is_active ? "재직" : "제외" }}</td>
            <td>{{ item.worker.sanction_status_label }}</td>
            <td>
              <template v-if="item.worker.history_visible">
                <ul v-if="item.sanctions.length" class="history">
                  <li v-for="s in item.sanctions" :key="s.id">{{ s.violation_label }} → {{ s.sanction_result_label }}</li>
                </ul>
                <span v-else>—</span>
              </template>
              <span v-else class="muted">영구퇴출 (요약만)</span>
            </td>
            <td class="muted">{{ item.worker.mileage?.message || "준비중" }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <div v-if="historyModal" class="modal-backdrop" @click.self="historyModal = null">
      <div class="modal">
        <h3>{{ historyModal.worker?.name }} — 제재 이력</h3>
        <p v-if="!historyModal.history_visible" class="warn">{{ historyModal.message }}</p>
        <ul v-else class="history-full">
          <li v-for="s in allSanctions" :key="`${s.id}-${s.from_prior_period}`">
            <span v-if="s.from_prior_period" class="tag">이전 회차</span>
            {{ s.created_at }} · {{ s.violation_label }} → {{ s.sanction_result_label }} ({{ s.strike_number }}차)
            <span v-if="s.note" class="note"> — {{ s.note }}</span>
          </li>
        </ul>
        <section class="mileage-box">
          <h4>마일리지 (운영 준비)</h4>
          <p>{{ historyModal.mileage?.message }}</p>
          <p class="meta">적립 포인트: {{ historyModal.mileage?.points ?? 0 }} (추후 연동)</p>
        </section>
        <button class="stitch-btn-secondary" type="button" @click="historyModal = null">닫기</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";

interface Period {
  id: number;
  deadline_date: string;
  is_closed: boolean;
}

interface DiffResult {
  new_count: number;
  updated_count: number;
  unchanged_count: number;
  removed_count: number;
  parsed_rows: number;
  items: Array<{
    type: string;
    name: string;
    site_code: string;
    changes?: Record<string, [unknown, unknown]>;
  }>;
}

const period = ref<Period | null>(null);
const items = ref<Array<{ worker: Record<string, unknown>; sanctions: unknown[] }>>([]);
const deadlineInput = ref("");
const sortBy = ref("site_code");
const sortDir = ref("asc");
const includeInactive = ref(false);
const rosterFile = ref<File | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const diffing = ref(false);
const applying = ref(false);
const diffResult = ref<DiffResult | null>(null);
const applyResult = ref("");

const historyModal = ref<{
  worker: { name: string };
  history_visible: boolean;
  message?: string;
  sanctions: unknown[];
  prior_sanctions: unknown[];
  mileage: { message?: string; points?: number };
} | null>(null);

const diffPreviewItems = computed(() => (diffResult.value?.items || []).slice(0, 50));

const allSanctions = computed(() => {
  if (!historyModal.value?.history_visible) return [];
  return [...(historyModal.value.prior_sanctions || []), ...(historyModal.value.sanctions || [])];
});

function diffTypeLabel(t: string) {
  const map: Record<string, string> = {
    NEW: "신규",
    UPDATED: "변경",
    UNCHANGED: "동일",
    REMOVED: "명부제외",
  };
  return map[t] || t;
}

function formatChanges(changes?: Record<string, [unknown, unknown]>) {
  if (!changes) return "—";
  return Object.entries(changes)
    .map(([k, v]) => `${k}: ${v[0]} → ${v[1]}`)
    .join(", ");
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  rosterFile.value = input.files?.[0] || null;
  diffResult.value = null;
  applyResult.value = "";
}

async function uploadFile(endpoint: string) {
  const form = new FormData();
  form.append("file", rosterFile.value!);
  return api.post(endpoint, form);
}

async function runDiff() {
  if (!rosterFile.value) return;
  diffing.value = true;
  try {
    const res = await uploadFile("/functional-eval/hq/roster/diff");
    diffResult.value = res.data;
    period.value = res.data.period;
    deadlineInput.value = period.value?.deadline_date || "";
  } finally {
    diffing.value = false;
  }
}

async function applyRoster() {
  if (!rosterFile.value) return;
  applying.value = true;
  applyResult.value = "";
  try {
    const res = await uploadFile("/functional-eval/hq/roster/apply");
    applyResult.value = `반영 완료 — 신규 ${res.data.new_count}, 변경 ${res.data.updated_count}, 제외 ${res.data.removed_count}`;
    diffResult.value = null;
    rosterFile.value = null;
    if (fileInput.value) fileInput.value.value = "";
    await load();
  } finally {
    applying.value = false;
  }
}

async function load() {
  const params: Record<string, string | boolean> = {
    sort_by: sortBy.value,
    sort_dir: sortDir.value,
    include_inactive: includeInactive.value,
  };
  const res = await api.get("/functional-eval/hq/summary", { params });
  period.value = res.data.period;
  items.value = res.data.items || [];
  deadlineInput.value = period.value?.deadline_date || "";
}

async function saveDeadline() {
  if (!period.value || !deadlineInput.value) return;
  await api.patch(`/functional-eval/period/${period.value.id}/deadline`, {
    deadline_date: deadlineInput.value,
  });
  await load();
}

async function openHistory(workerId: number) {
  const res = await api.get(`/functional-eval/workers/${workerId}/history`);
  historyModal.value = res.data;
}

async function downloadExport() {
  const res = await api.get("/functional-eval/hq/export", {
    params: { sort_by: sortBy.value, sort_dir: sortDir.value },
    responseType: "blob",
  });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = "functional_eval_sanctions.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}

onMounted(load);
</script>

<style scoped>
.fe-hq-page { display: flex; flex-direction: column; gap: 16px; }
.page-head { display: flex; justify-content: space-between; }
.panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.panel-sub { color: #64748b; font-size: 13px; margin: 0 0 8px; }
.row { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; margin-top: 8px; }
.toolbar { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; align-items: flex-end; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table.compact { font-size: 13px; }
.data-table th, .data-table td { border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; vertical-align: top; }
.history { margin: 0; padding-left: 16px; font-size: 13px; }
.diff-summary { display: flex; gap: 12px; margin-top: 12px; font-size: 14px; }
.diff-type.NEW { color: #166534; }
.diff-type.UPDATED { color: #92400e; }
.diff-type.REMOVED { color: #991b1b; }
.badge { padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.badge.open { background: #dcfce7; color: #166534; }
.badge.closed { background: #fee2e2; color: #991b1b; }
.meta { color: #64748b; font-size: 13px; }
.meta.success { color: #166534; }
.muted { color: #94a3b8; font-size: 13px; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 12px; padding: 20px; max-width: 560px; width: 90%; max-height: 80vh; overflow: auto; }
.history-full { padding-left: 18px; font-size: 13px; }
.mileage-box { margin-top: 16px; padding: 12px; background: #f8fafc; border-radius: 8px; }
.tag { font-size: 11px; background: #e2e8f0; padding: 1px 6px; border-radius: 4px; margin-right: 4px; }
.warn { color: #991b1b; }
.checkbox-label { display: flex; align-items: center; gap: 6px; }
</style>
