<template>
  <div class="calendar-page card">
    <div class="header-row">
      <div class="card-title">안전교육 및 안전점검</div>
      <div class="nav-row">
        <button type="button" class="secondary" @click="shiftMonth(-1)">이전 달</button>
        <span class="ym-label">{{ year }}년 {{ month }}월</span>
        <button type="button" class="secondary" @click="shiftMonth(1)">다음 달</button>
        <button v-if="isHq" type="button" class="primary plus-btn" title="일정 등록" @click="openCreateEntry">+ 일정 등록</button>
        <button type="button" class="secondary" @click="reload">새로고침</button>
      </div>
    </div>
    <p class="hint">
      삼성물산 안전인정제 스케줄표(NAVER WORKS) 기준 일정입니다. 셀에는 요약 제목이 표시되며,
      <strong>파란 점은 오늘 이후 미확인 일정</strong>만 표시됩니다(오늘 전 일정은 확인된 것으로 간주).
      날짜를 누르면 상세·점검(담당)자를 볼 수 있습니다.
    </p>

    <div class="weekday-row">
      <span v-for="w in weekdays" :key="w" class="weekday-cell">{{ w }}</span>
    </div>
    <div class="grid">
      <div
        v-for="cell in cells"
        :key="cell.key"
        class="cell"
        :class="{
          muted: !cell.inMonth,
          has: cell.pendingEntries.length > 0,
          today: cell.isToday,
        }"
        @click="cell.inMonth && openDay(cell)"
      >
        <div class="day-num">{{ cell.day }}</div>
        <div v-if="cell.entries.length" class="cell-summaries">
          <div v-for="e in cell.entries.slice(0, 2)" :key="e.id" class="cell-sum-line" :title="e.title">
            {{ e.shortTitle }}
          </div>
          <div v-if="cell.entries.length > 2" class="cell-sum-more">+{{ cell.entries.length - 2 }}</div>
        </div>
        <div v-if="cell.pendingEntries.length" class="dots">
          <span v-for="e in cell.pendingEntries.slice(0, 3)" :key="e.id" class="dot" :title="e.title" />
          <span v-if="cell.pendingEntries.length > 3" class="more">+{{ cell.pendingEntries.length - 3 }}</span>
        </div>
      </div>
    </div>

    <section v-if="isHq" class="pending-section">
      <h3>일정 변경 제안 (본사 승인 대기)</h3>
      <p v-if="pendingLoading" class="muted">불러오는 중…</p>
      <table v-else-if="pendingItems.length" class="basic-table">
        <thead>
          <tr>
            <th>일정</th>
            <th>현재일</th>
            <th>제안일</th>
            <th>제안자</th>
            <th>비고</th>
            <th>처리</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in pendingItems" :key="p.proposal_id">
            <td>{{ p.entry_title }}</td>
            <td>{{ p.current_date }}</td>
            <td>{{ p.proposed_date }}</td>
            <td>{{ p.proposed_by_name }} ({{ p.proposed_by_login }})</td>
            <td>{{ p.comment || "—" }}</td>
            <td class="action-cell">
              <button type="button" class="primary sm" @click="approve(p.proposal_id)">승인</button>
              <button type="button" class="secondary sm" @click="reject(p.proposal_id)">반려</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">대기 중인 제안이 없습니다.</p>
    </section>

    <div v-if="dayModal" class="modal-backdrop" @click.self="closeDay">
      <div class="modal-box wide">
        <h4 class="modal-title">{{ selectedIso }} 일정</h4>
        <div v-if="dayDetailLoading" class="muted">불러오는 중…</div>
        <template v-else>
          <div v-for="row in dayModalRows" :key="row.id" class="entry-block">
            <div class="entry-head">
              <strong>{{ shortSafetyScheduleLabel(row.title) }}</strong>
              <span class="badge" v-if="row.has_pending">제안 대기</span>
            </div>
            <template v-if="isHq">
              <div class="inline-edit-grid">
                <label>
                  <span>일자</span>
                  <input v-model="row.edit_date" type="date" class="date-inp" />
                </label>
                <label>
                  <span>제목</span>
                  <input v-model="row.edit_title" type="text" class="text-inp wide" placeholder="예: 안전실 점검" />
                </label>
                <label>
                  <span>점검(담당)자</span>
                  <input v-model="row.edit_inspector" type="text" class="text-inp" />
                </label>
                <label>
                  <span>상세</span>
                  <textarea v-model="row.edit_detail" class="detail-ta" rows="3" />
                </label>
              </div>
              <div class="entry-actions">
                <button
                  type="button"
                  class="primary sm"
                  :disabled="!row.edit_date || !row.edit_title.trim() || savingEntryId === row.id"
                  @click="saveEntry(row)"
                >
                  {{ savingEntryId === row.id ? "저장 중…" : "저장" }}
                </button>
              </div>
            </template>
            <template v-else>
              <div class="meta"><span>점검(담당)자</span> {{ row.inspector_label }}</div>
              <pre v-if="row.detail_text" class="detail-pre">{{ row.detail_text }}</pre>
            </template>
            <template v-if="isSite">
              <button type="button" class="secondary sm" @click="togglePropose(row)">의견 제시 (일정 변경)</button>
              <div v-if="proposeEntryId === row.id" class="propose-box">
                <label>변경 희망일</label>
                <input v-model="proposeDate" type="date" class="date-inp" />
                <label>코멘트 (선택)</label>
                <input v-model="proposeComment" type="text" class="text-inp" placeholder="현장 사정 등" />
                <button type="button" class="primary sm" :disabled="!proposeDate || proposing" @click="submitPropose(row.id)">
                  {{ proposing ? "제출 중…" : "제출" }}
                </button>
              </div>
            </template>
          </div>
          <div v-if="!dayModalRows.length" class="muted">이 날짜에 등록된 일정이 없습니다.</div>
        </template>
        <div class="modal-actions">
          <button type="button" class="secondary" @click="closeDay">닫기</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { todayKst } from "@/utils/datetime";
import { cleanSafetyScheduleTitle, shortSafetyScheduleLabel } from "@/utils/safetyScheduleLabels";

const auth = useAuthStore();
const weekdays = ["일", "월", "화", "수", "목", "금", "토"];

const now = new Date();
const year = ref(now.getFullYear());
const month = ref(now.getMonth() + 1);

type ScheduleRow = {
  id: number;
  scheduled_date: string;
  title: string;
  shortTitle: string;
  inspector_label: string;
  has_pending_proposal: boolean;
};

const items = ref<ScheduleRow[]>([]);
const loading = ref(false);

const dayModal = ref(false);
const selectedIso = ref("");
const dayModalRows = ref<
  Array<{
    id: number;
    title: string;
    scheduled_date: string;
    inspector_label: string;
    detail_text: string | null;
    has_pending: boolean;
    edit_date: string;
    edit_title: string;
    edit_inspector: string;
    edit_detail: string;
  }>
>([]);
const dayDetailLoading = ref(false);
const savingEntryId = ref<number | null>(null);

const proposeEntryId = ref<number | null>(null);
const proposeDate = ref("");
const proposeComment = ref("");
const proposing = ref(false);

const pendingItems = ref<
  Array<{
    proposal_id: number;
    entry_id: number;
    entry_title: string;
    current_date: string;
    proposed_date: string;
    comment: string | null;
    proposed_by_name: string;
    proposed_by_login: string;
  }>
>([]);
const pendingLoading = ref(false);

const isHq = computed(() =>
  ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN", "ACCIDENT_ADMIN"].includes(auth.user?.role ?? ""),
);
const isSite = computed(() => auth.user?.role === "SITE");

interface Cell {
  key: string;
  day: number;
  inMonth: boolean;
  isToday: boolean;
  iso: string;
  entries: ScheduleRow[];
  pendingEntries: ScheduleRow[];
}

const cells = computed(() => {
  const y = year.value;
  const m = month.value;
  const first = new Date(y, m - 1, 1);
  const startWeekday = first.getDay();
  const lastDate = new Date(y, m, 0).getDate();
  const map = new Map<string, ScheduleRow[]>();
  for (const it of items.value) {
    const arr = map.get(it.scheduled_date) ?? [];
    arr.push(it);
    map.set(it.scheduled_date, arr);
  }
  const out: Cell[] = [];
  const pad = startWeekday;
  const prevLast = new Date(y, m - 1, 0).getDate();
  for (let i = 0; i < pad; i++) {
    const d = prevLast - pad + i + 1;
    out.push({ key: `p-${d}`, day: d, inMonth: false, isToday: false, iso: "", entries: [], pendingEntries: [] });
  }
  const today = todayKst();
  for (let d = 1; d <= lastDate; d++) {
    const iso = `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const all = map.get(iso) ?? [];
    const pending = iso >= today ? all : [];
    out.push({
      key: `c-${d}`,
      day: d,
      inMonth: true,
      isToday: iso === today,
      iso,
      entries: all,
      pendingEntries: pending,
    });
  }
  let nextMonthDay = 1;
  while (out.length % 7 !== 0 || out.length < 42) {
    out.push({
      key: `n-${nextMonthDay}`,
      day: nextMonthDay,
      inMonth: false,
      isToday: false,
      iso: "",
      entries: [],
      pendingEntries: [],
    });
    nextMonthDay += 1;
  }
  return out;
});

async function loadMonth() {
  loading.value = true;
  try {
    const res = await api.get("/safety-features/schedule/entries", {
      params: { year: year.value, month: month.value },
    });
    const list = (res.data.items ?? []) as Array<{
      id: number;
      scheduled_date: string;
      title: string;
      inspector_label: string;
      has_pending_proposal: boolean;
    }>;
    items.value = list.map((it) => ({
      ...it,
      shortTitle: shortSafetyScheduleLabel(it.title),
    }));
  } catch {
    items.value = [];
  } finally {
    loading.value = false;
  }
}

async function loadPending() {
  if (!isHq.value) return;
  pendingLoading.value = true;
  try {
    const res = await api.get("/safety-features/schedule/proposals/pending");
    pendingItems.value = res.data.items ?? [];
  } catch {
    pendingItems.value = [];
  } finally {
    pendingLoading.value = false;
  }
}

function shiftMonth(delta: number) {
  let m = month.value + delta;
  let y = year.value;
  while (m > 12) {
    m -= 12;
    y += 1;
  }
  while (m < 1) {
    m += 12;
    y -= 1;
  }
  month.value = m;
  year.value = y;
}

function reload() {
  void loadMonth();
  void loadPending();
}

function openCreateEntry() {
  const base = `${year.value}-${String(month.value).padStart(2, "0")}-01`;
  dayModal.value = true;
  selectedIso.value = "신규 일정";
  dayDetailLoading.value = false;
  dayModalRows.value = [
    {
      id: -1,
      title: "",
      scheduled_date: base,
      inspector_label: "-",
      detail_text: null,
      has_pending: false,
      edit_date: base,
      edit_title: "",
      edit_inspector: "-",
      edit_detail: "",
    },
  ];
}

async function openDay(cell: Cell) {
  if (!cell.inMonth) return;
  const y = year.value;
  const m = month.value;
  const iso = `${y}-${String(m).padStart(2, "0")}-${String(cell.day).padStart(2, "0")}`;
  selectedIso.value = iso;
  dayModal.value = true;
  proposeEntryId.value = null;
  proposeDate.value = "";
  proposeComment.value = "";
  dayDetailLoading.value = true;
  dayModalRows.value = [];
  const dayItems = cell.entries;
  try {
    const rows: typeof dayModalRows.value = [];
    for (const it of dayItems) {
      const res = await api.get(`/safety-features/schedule/entries/${it.id}`);
      const pend = (res.data.proposals ?? []).some((x: { status: string }) => x.status === "PENDING");
      rows.push({
        id: res.data.id,
        title: res.data.title,
        scheduled_date: res.data.scheduled_date,
        inspector_label: res.data.inspector_label,
        detail_text: res.data.detail_text,
        has_pending: pend,
        edit_date: res.data.scheduled_date,
        edit_title: cleanSafetyScheduleTitle(res.data.title),
        edit_inspector: res.data.inspector_label,
        edit_detail: res.data.detail_text ?? "",
      });
    }
    dayModalRows.value = rows;
  } finally {
    dayDetailLoading.value = false;
  }
}

function closeDay() {
  dayModal.value = false;
}

function togglePropose(row: { id: number }) {
  proposeEntryId.value = proposeEntryId.value === row.id ? null : row.id;
}

async function submitPropose(entryId: number) {
  if (!proposeDate.value) return;
  proposing.value = true;
  try {
    await api.post("/safety-features/schedule/proposals", {
      entry_id: entryId,
      proposed_date: proposeDate.value,
      comment: proposeComment.value.trim() || null,
    });
    proposeEntryId.value = null;
    proposeDate.value = "";
    proposeComment.value = "";
    await loadMonth();
    await loadPending();
    closeDay();
  } catch (e: unknown) {
    const ax = e as { response?: { data?: { detail?: string } } };
    window.alert(ax.response?.data?.detail ?? "제출에 실패했습니다.");
  } finally {
    proposing.value = false;
  }
}

async function approve(proposalId: number) {
  if (!window.confirm("제안 일정으로 확정할까요?")) return;
  try {
    await api.post(`/safety-features/schedule/proposals/${proposalId}/approve`);
    await loadMonth();
    await loadPending();
  } catch (e: unknown) {
    const ax = e as { response?: { data?: { detail?: string } } };
    window.alert(ax.response?.data?.detail ?? "승인 실패");
  }
}

async function reject(proposalId: number) {
  const note = window.prompt("반려 사유(선택)") ?? "";
  try {
    await api.post(`/safety-features/schedule/proposals/${proposalId}/reject`, null, {
      params: { decision_note: note || undefined },
    });
    await loadPending();
  } catch (e: unknown) {
    const ax = e as { response?: { data?: { detail?: string } } };
    window.alert(ax.response?.data?.detail ?? "반려 실패");
  }
}

async function saveEntry(row: (typeof dayModalRows.value)[number]) {
  if (!row.edit_date || !row.edit_title.trim()) return;
  const payload = {
    scheduled_date: row.edit_date,
    title: cleanSafetyScheduleTitle(row.edit_title.trim()),
    inspector_label: row.edit_inspector.trim() || "-",
    detail_text: row.edit_detail.trim() || null,
  };
  savingEntryId.value = row.id;
  try {
    if (row.id < 0) {
      await api.post("/safety-features/schedule/entries", payload);
    } else {
      await api.put(`/safety-features/schedule/entries/${row.id}`, payload);
    }
    const [y, m] = row.edit_date.split("-").map(Number);
    if (y && m) {
      year.value = y;
      month.value = m;
    }
    await loadMonth();
    closeDay();
    window.alert("저장되었습니다.");
  } catch (e: unknown) {
    const ax = e as { response?: { data?: { detail?: string } } };
    window.alert(ax.response?.data?.detail ?? "저장에 실패했습니다.");
  } finally {
    savingEntryId.value = null;
  }
}

watch([year, month], () => {
  void loadMonth();
});

onMounted(() => {
  void loadMonth();
  void loadPending();
});
</script>

<style scoped>
.calendar-page {
  max-width: 1100px;
}
.header-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.nav-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.plus-btn {
  height: 30px;
  padding: 0 10px;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}
.ym-label {
  font-weight: 700;
  min-width: 120px;
  text-align: center;
}
.hint {
  color: #64748b;
  font-size: 13px;
  margin: 0 0 12px;
}
.small {
  font-size: 13px;
  margin: 0 0 10px;
}
.weekday-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
  margin-bottom: 4px;
}
.weekday-cell {
  text-align: center;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}
.grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}
.cell {
  min-height: 104px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 6px;
  cursor: pointer;
  background: #fff;
}
.cell-summaries {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 0;
}
.cell-sum-line {
  font-size: 10px;
  line-height: 1.25;
  color: #334155;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cell-sum-more {
  font-size: 10px;
  color: #64748b;
}
.cell.muted {
  background: #f8fafc;
  color: #94a3b8;
  cursor: default;
}
.cell.has {
  border-color: #93c5fd;
  background: #eff6ff;
}
.cell.today {
  outline: 2px solid #2563eb;
}
.day-num {
  font-weight: 700;
  font-size: 13px;
}
.dots {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  align-items: center;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 99px;
  background: #2563eb;
}
.more {
  font-size: 11px;
  color: #2563eb;
  margin-left: 2px;
}
.pending-section {
  margin-top: 24px;
}
.pending-section h3 {
  font-size: 15px;
  margin: 0 0 8px;
}
.basic-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.basic-table th,
.basic-table td {
  border: 1px solid #e2e8f0;
  padding: 6px 8px;
  text-align: left;
}
.basic-table th {
  background: #f1f5f9;
}
.action-cell {
  display: flex;
  gap: 6px;
}
.manual-section {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid #e2e8f0;
}
.manual-section h3 {
  margin: 0 0 6px;
  font-size: 16px;
}
.manual-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 520px;
}
.mf-row {
  display: grid;
  grid-template-columns: 120px 1fr;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.mf-row.mf-top {
  align-items: start;
}
.mf-row span {
  color: #475569;
}
.mf-actions {
  margin-top: 4px;
}
.date-inp,
.text-inp {
  padding: 6px 8px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 13px;
}
.text-inp.wide {
  width: 100%;
}
.detail-ta {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-family: inherit;
  font-size: 13px;
  resize: vertical;
}
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal-box {
  background: #fff;
  border-radius: 10px;
  padding: 18px;
  width: min(640px, 92vw);
  max-height: 84vh;
  overflow: auto;
}
.modal-box.wide {
  width: min(720px, 94vw);
}
.modal-title {
  margin: 0 0 12px;
  font-size: 16px;
}
.entry-block {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
  background: #fff;
}
.entry-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.inline-edit-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
  margin-bottom: 8px;
}
.inline-edit-grid label {
  display: grid;
  grid-template-columns: 92px 1fr;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #475569;
}
.entry-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
.badge {
  background: #fde68a;
  color: #92400e;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 11px;
}
.meta {
  font-size: 12px;
  color: #475569;
  margin-bottom: 4px;
}
.meta span {
  color: #94a3b8;
  margin-right: 4px;
}
.orig-title {
  font-size: 11px;
  color: #64748b;
  white-space: pre-wrap;
  margin-bottom: 4px;
}
.detail-pre {
  background: #f8fafc;
  border-radius: 6px;
  padding: 8px;
  font-size: 12px;
  white-space: pre-wrap;
  margin: 4px 0 8px;
}
.propose-box {
  margin-top: 8px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 4px;
  border-top: 1px dashed #cbd5e1;
  padding-top: 8px;
}
.propose-box label {
  font-size: 12px;
  color: #475569;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.muted {
  color: #94a3b8;
  font-size: 13px;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.card-title {
  font-size: 18px;
  font-weight: 700;
}
button.sm {
  font-size: 12px;
  padding: 4px 8px;
}
button.primary {
  background: #2563eb;
  color: #fff;
  border: 0;
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
}
button.secondary {
  background: #fff;
  color: #0f172a;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 6px 10px;
  cursor: pointer;
}
</style>
