<template>
  <div class="team-schedule-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">안전보건실 공용</p>
        <h2>팀 스케줄</h2>
        <p class="subtitle">로그인 권한이 부여된 팀원만 같은 일정을 조회합니다.</p>
        <p v-if="members.length" class="member-line">참여: {{ members.map((member) => member.name).join(" · ") }}</p>
      </div>
      <div class="month-nav">
        <button type="button" class="secondary" @click="shiftMonth(-1)">이전</button>
        <strong>{{ year }}년 {{ month }}월</strong>
        <button type="button" class="secondary" @click="shiftMonth(1)">다음</button>
        <button type="button" class="secondary" :disabled="loading" @click="reload">새로고침</button>
      </div>
    </header>

    <p v-if="isMobileSurface" class="surface-notice mobile-notice">
      모바일·태블릿은 현재 조회 전용입니다. 일정 등록·수정·완료 처리는 PC에서 할 수 있습니다.
    </p>
    <p v-else-if="capabilities && !capabilities.can_write" class="surface-notice">
      이 계정은 팀 스케줄을 조회할 수 있지만 PC 편집 권한은 없습니다.
    </p>
    <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
    <p v-if="statusMessage" class="status-message" role="status">{{ statusMessage }}</p>

    <div class="workspace" :class="{ 'workspace--read-only': !canWrite }">
      <section v-if="canWrite" class="editor-card">
        <div class="editor-title-row">
          <h3>{{ form.public_id ? "일정 수정" : "새 일정" }}</h3>
          <button type="button" class="secondary compact" @click="startNewItem">새 항목</button>
        </div>
        <p v-if="form.public_id && !form.can_edit" class="owner-notice">
          {{ form.owner_name || "다른 팀원" }}의 일정입니다. 내용은 읽을 수 있고 댓글만 추가할 수 있습니다.
        </p>
        <label>
          <span>날짜</span>
          <input v-model="form.scheduled_date" type="date" :disabled="!canEditCurrent" />
        </label>
        <label>
          <span>제목</span>
          <input v-model="form.title" type="text" maxlength="300" placeholder="업무 일정을 입력하세요" :disabled="!canEditCurrent" />
        </label>
        <label>
          <span>상태</span>
          <select v-model="form.status" :disabled="!canEditCurrent">
            <option v-for="option in statusOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>
        <p class="owner-help">일정 소유자와 담당자는 로그인한 본인으로 고정됩니다.</p>
        <label>
          <span>상세</span>
          <textarea v-model="form.detail_text" rows="6" maxlength="20000" placeholder="관련 업무, 준비사항, 메모" :disabled="!canEditCurrent" />
        </label>
        <div class="editor-actions">
          <button type="button" class="primary" :disabled="saving || !canSave || !canEditCurrent" @click="saveItem">
            {{ saving ? "저장 중…" : "저장" }}
          </button>
          <button
            v-if="form.public_id && form.can_edit && form.status !== 'COMPLETED'"
            type="button"
            class="complete"
            :disabled="saving"
            @click="completeItem"
          >
            완료 처리
          </button>
          <button
            v-if="form.public_id && form.can_edit"
            type="button"
            class="danger-link"
            :disabled="saving"
            @click="archiveItem"
          >
            보관
          </button>
        </div>
        <div v-if="form.public_id" class="comment-panel">
          <h4>댓글</h4>
          <p v-if="!comments.length" class="comment-empty">등록된 댓글이 없습니다.</p>
          <ul v-else>
            <li v-for="comment in comments" :key="comment.public_id">
              <strong>{{ comment.author_name || "팀원" }}</strong>
              <span>{{ comment.body_text }}</span>
            </li>
          </ul>
          <textarea v-model="commentDraft" rows="3" maxlength="4000" placeholder="이 일정에 대한 코멘트" />
          <button type="button" class="secondary" :disabled="saving || !commentDraft.trim()" @click="addComment">댓글 등록</button>
        </div>
        <p class="editor-help">동시 수정 충돌이 감지되면 최신 내용을 다시 불러온 뒤 저장하도록 안내합니다.</p>
      </section>

      <section class="calendar-card">
        <div v-if="loading" class="empty-state">일정을 불러오는 중입니다…</div>

        <template v-else-if="useAgendaLayout">
          <div v-if="items.length" class="mobile-agenda">
            <article v-for="row in items" :key="row.public_id" class="agenda-item">
              <button
                type="button"
                class="agenda-summary"
                :aria-expanded="expandedId === row.public_id"
                @click="toggleExpanded(row.public_id)"
              >
                <span class="agenda-date">{{ compactDate(row.scheduled_date) }}</span>
                <span class="agenda-main">
                  <strong>{{ row.title }}</strong>
                  <small>{{ statusLabel(row.status) }} · {{ row.owner_name || row.assigned_user_name || "소유자 미확인" }}</small>
                </span>
                <span aria-hidden="true">{{ expandedId === row.public_id ? "−" : "+" }}</span>
              </button>
              <div v-if="expandedId === row.public_id" class="agenda-detail">
                <p>{{ row.detail_text || "상세 메모가 없습니다." }}</p>
                <small>최종 수정: {{ row.updated_by_name || "-" }} · {{ formatUpdatedAt(row.updated_at) }}</small>
                <button v-if="canWrite" type="button" class="secondary compact" @click="selectItem(row)">
                  {{ row.can_edit ? "이 일정 편집" : "상세·댓글" }}
                </button>
              </div>
            </article>
          </div>
          <div v-else class="empty-state">이 달에 등록된 팀 일정이 없습니다.</div>
        </template>

        <template v-else>
          <div class="weekday-row">
            <span v-for="weekday in weekdays" :key="weekday">{{ weekday }}</span>
          </div>
          <div class="calendar-grid">
            <div
              v-for="cell in calendarCells"
              :key="cell.key"
              class="day-cell"
              :class="{ muted: !cell.inMonth, today: cell.iso === todayIso }"
            >
              <span class="day-number">{{ cell.day }}</span>
              <div class="day-items">
                <button
                  v-for="row in cell.items"
                  :key="row.public_id"
                  type="button"
                  class="schedule-chip"
                  :class="`status-${row.status.toLowerCase()}`"
                  :title="`${row.title} · ${row.owner_name || row.assigned_user_name || '소유자 미확인'}`"
                  @click="selectItem(row)"
                >
                  <span>{{ row.title }}</span>
                  <small>{{ row.owner_name || row.assigned_user_name || "소유자 미확인" }}</small>
                </button>
              </div>
            </div>
          </div>
          <div v-if="!items.length" class="empty-state desktop-empty">이 달에 등록된 팀 일정이 없습니다.</div>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { useMobileViewport } from "@/composables/useMobileViewport";
import { api } from "@/services/api";
import { todayKst } from "@/utils/datetime";

type ScheduleStatus = "PLANNED" | "IN_PROGRESS" | "COMPLETED" | "ON_HOLD";

type ScheduleItem = {
  public_id: string;
  client_item_key: string | null;
  scheduled_date: string;
  title: string;
  detail_text: string | null;
  status: ScheduleStatus;
  assigned_user_id: number | null;
  assigned_user_name: string | null;
  owner_user_id: number;
  owner_name: string | null;
  can_edit: boolean;
  revision: number;
  updated_at: string;
  updated_by_name: string | null;
};

type ScheduleComment = {
  public_id: string;
  author_user_id: number;
  author_name: string | null;
  body_text: string;
  created_at: string;
};

type Member = {
  user_id: number;
  name: string;
};

type Capabilities = {
  can_read: boolean;
  can_write: boolean;
  surface: "PC_WEB" | "MOBILE_WEB" | "SAFETY_WORKBENCH";
  pc_writes_enabled: boolean;
  mobile_writes_enabled: boolean;
};

const CLIENT_INSTANCE_STORAGE_KEY = "besma_team_schedule_client_instance_id";
const PENDING_CREATE_KEY_STORAGE_KEY = "besma_team_schedule_pending_create_key";

function randomClientToken(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function clientInstanceId(): string {
  if (typeof window === "undefined") return randomClientToken();
  try {
    const existing = window.localStorage.getItem(CLIENT_INSTANCE_STORAGE_KEY)?.trim();
    if (existing) return existing;
    const created = randomClientToken();
    window.localStorage.setItem(CLIENT_INSTANCE_STORAGE_KEY, created);
    return created;
  } catch {
    return randomClientToken();
  }
}

function readMobileDevice(): boolean {
  if (typeof navigator === "undefined") return false;
  const nav = navigator as Navigator & { userAgentData?: { mobile?: boolean } };
  if (nav.userAgentData?.mobile === true) return true;
  if (/Android|iPhone|iPad|iPod|Windows Phone|Mobile/i.test(nav.userAgent)) return true;
  return /Macintosh/i.test(nav.userAgent) && nav.maxTouchPoints > 1;
}

const scheduleClientInstanceId = clientInstanceId();

function makeClientItemKey(): string {
  return `web:${scheduleClientInstanceId}:${randomClientToken()}`;
}

function pendingClientItemKey(): string {
  if (typeof window === "undefined") return makeClientItemKey();
  try {
    const existing = window.sessionStorage.getItem(PENDING_CREATE_KEY_STORAGE_KEY)?.trim();
    if (existing) return existing;
    const created = makeClientItemKey();
    window.sessionStorage.setItem(PENDING_CREATE_KEY_STORAGE_KEY, created);
    return created;
  } catch {
    return makeClientItemKey();
  }
}

function rotatePendingClientItemKey(): string {
  const created = makeClientItemKey();
  if (typeof window !== "undefined") {
    try {
      window.sessionStorage.setItem(PENDING_CREATE_KEY_STORAGE_KEY, created);
    } catch {
      // Storage can be disabled; the in-memory key still preserves retries in this page session.
    }
  }
  return created;
}

const { isMobileViewport: isCompactViewport } = useMobileViewport();
const isMobileDevice = ref(readMobileDevice());
const todayIso = todayKst();
const [initialYear, initialMonth] = todayIso.split("-").map(Number);
const year = ref(initialYear);
const month = ref(initialMonth);
const items = ref<ScheduleItem[]>([]);
const members = ref<Member[]>([]);
const capabilities = ref<Capabilities | null>(null);
const loading = ref(false);
const saving = ref(false);
const errorMessage = ref("");
const statusMessage = ref("");
const expandedId = ref<string | null>(null);
const comments = ref<ScheduleComment[]>([]);
const commentDraft = ref("");

const statusOptions: Array<{ value: ScheduleStatus; label: string }> = [
  { value: "PLANNED", label: "예정" },
  { value: "IN_PROGRESS", label: "진행" },
  { value: "COMPLETED", label: "완료" },
  { value: "ON_HOLD", label: "보류" },
];
const weekdays = ["일", "월", "화", "수", "목", "금", "토"];

const form = reactive<{
  public_id: string | null;
  revision: number | null;
  scheduled_date: string;
  title: string;
  detail_text: string;
  status: ScheduleStatus;
  assigned_user_id: number | null;
  owner_name: string | null;
  can_edit: boolean;
  client_item_key: string;
}>({
  public_id: null,
  revision: null,
  scheduled_date: todayIso,
  title: "",
  detail_text: "",
  status: "PLANNED",
  assigned_user_id: null,
  owner_name: null,
  can_edit: true,
  client_item_key: pendingClientItemKey(),
});

const isMobileSurface = computed(() => isMobileDevice.value);
const useAgendaLayout = computed(() => isCompactViewport.value || isMobileSurface.value);
const surface = computed<"PC_WEB" | "MOBILE_WEB">(() =>
  isMobileSurface.value ? "MOBILE_WEB" : "PC_WEB",
);
const canWrite = computed(() => capabilities.value?.can_write === true);
const canSave = computed(() => !!form.scheduled_date && !!form.title.trim());
const canEditCurrent = computed(() => canWrite.value && (!form.public_id || form.can_edit));

function formSignature(): string {
  return JSON.stringify({
    public_id: form.public_id,
    revision: form.revision,
    scheduled_date: form.scheduled_date,
    title: form.title,
    detail_text: form.detail_text,
    status: form.status,
    assigned_user_id: form.assigned_user_id,
  });
}

const baselineSignature = ref(formSignature());
const isDirty = computed(
  () => formSignature() !== baselineSignature.value || !!commentDraft.value.trim(),
);

const monthStart = computed(() => `${year.value}-${String(month.value).padStart(2, "0")}-01`);
const monthEnd = computed(() => {
  const day = new Date(year.value, month.value, 0).getDate();
  return `${year.value}-${String(month.value).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
});

type CalendarCell = {
  key: string;
  day: number;
  iso: string;
  inMonth: boolean;
  items: ScheduleItem[];
};

const calendarCells = computed<CalendarCell[]>(() => {
  const firstWeekday = new Date(year.value, month.value - 1, 1).getDay();
  const lastDay = new Date(year.value, month.value, 0).getDate();
  const previousLastDay = new Date(year.value, month.value - 1, 0).getDate();
  const byDate = new Map<string, ScheduleItem[]>();
  for (const row of items.value) {
    const list = byDate.get(row.scheduled_date) ?? [];
    list.push(row);
    byDate.set(row.scheduled_date, list);
  }
  const cells: CalendarCell[] = [];
  for (let offset = firstWeekday; offset > 0; offset -= 1) {
    const day = previousLastDay - offset + 1;
    cells.push({ key: `previous-${day}`, day, iso: "", inMonth: false, items: [] });
  }
  for (let day = 1; day <= lastDay; day += 1) {
    const iso = `${year.value}-${String(month.value).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    cells.push({ key: iso, day, iso, inMonth: true, items: byDate.get(iso) ?? [] });
  }
  let nextDay = 1;
  while (cells.length < 42) {
    cells.push({ key: `next-${nextDay}`, day: nextDay, iso: "", inMonth: false, items: [] });
    nextDay += 1;
  }
  return cells;
});

function apiErrorMessage(error: unknown, fallback: string): string {
  const candidate = error as { response?: { data?: { detail?: string | { code?: string } } } };
  const detail = candidate.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail.code === "string") return detail.code;
  return fallback;
}

function statusLabel(value: ScheduleStatus): string {
  return statusOptions.find((option) => option.value === value)?.label ?? value;
}

function compactDate(value: string): string {
  const [, monthPart, dayPart] = value.split("-");
  return `${Number(monthPart)}월 ${Number(dayPart)}일`;
}

function formatUpdatedAt(value: string): string {
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  const parsed = new Date(hasTimezone ? value : `${value}Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function shiftMonth(delta: number) {
  if (!confirmEditorTransition()) return;
  let nextMonth = month.value + delta;
  let nextYear = year.value;
  while (nextMonth > 12) {
    nextMonth -= 12;
    nextYear += 1;
  }
  while (nextMonth < 1) {
    nextMonth += 12;
    nextYear -= 1;
  }
  year.value = nextYear;
  month.value = nextMonth;
  resetForm(`${nextYear}-${String(nextMonth).padStart(2, "0")}-01`);
}

function resetForm(dateValue = todayIso) {
  form.public_id = null;
  form.revision = null;
  form.scheduled_date = dateValue;
  form.title = "";
  form.detail_text = "";
  form.status = "PLANNED";
  form.assigned_user_id = null;
  form.owner_name = null;
  form.can_edit = true;
  form.client_item_key = rotatePendingClientItemKey();
  comments.value = [];
  commentDraft.value = "";
  baselineSignature.value = formSignature();
}

function confirmEditorTransition(
  message = "저장하지 않은 편집 내용이 있습니다. 변경 내용을 버리고 이동할까요?",
): boolean {
  if (saving.value) {
    statusMessage.value = "저장이 끝난 뒤 다시 시도해 주세요.";
    return false;
  }
  return !isDirty.value || window.confirm(message);
}

function startNewItem() {
  if (!confirmEditorTransition()) return;
  resetForm();
}

async function selectItem(row: ScheduleItem) {
  if (!canWrite.value || row.public_id === form.public_id) return;
  if (!confirmEditorTransition()) return;
  form.public_id = row.public_id;
  form.revision = row.revision;
  form.scheduled_date = row.scheduled_date;
  form.title = row.title;
  form.detail_text = row.detail_text ?? "";
  form.status = row.status;
  form.assigned_user_id = row.assigned_user_id;
  form.owner_name = row.owner_name;
  form.can_edit = row.can_edit;
  form.client_item_key = row.client_item_key ?? makeClientItemKey();
  baselineSignature.value = formSignature();
  try {
    await loadComments(row.public_id);
  } catch (error) {
    comments.value = [];
    errorMessage.value = apiErrorMessage(error, "댓글을 불러오지 못했습니다.");
  }
}

function toggleExpanded(publicId: string) {
  expandedId.value = expandedId.value === publicId ? null : publicId;
}

async function loadCapabilities() {
  const response = await api.get("/safety-features/team-schedule/capabilities", {
    params: { surface: surface.value },
  });
  capabilities.value = response.data as Capabilities;
}

async function loadMembers() {
  const response = await api.get("/safety-features/team-schedule/members");
  members.value = response.data.items ?? [];
}

async function loadItems() {
  const response = await api.get("/safety-features/team-schedule/items", {
    params: { from_date: monthStart.value, to_date: monthEnd.value },
  });
  items.value = response.data.items ?? [];
}

async function loadComments(publicId: string) {
  const response = await api.get(`/safety-features/team-schedule/items/${publicId}/comments`);
  comments.value = response.data.items ?? [];
}

async function reload() {
  loading.value = true;
  errorMessage.value = "";
  try {
    await Promise.all([loadCapabilities(), loadMembers(), loadItems()]);
  } catch (error) {
    capabilities.value = null;
    items.value = [];
    errorMessage.value = apiErrorMessage(error, "팀 스케줄을 불러오지 못했습니다.");
  } finally {
    loading.value = false;
  }
}

function writeHeaders() {
  return { "X-BESMA-Client-Surface": surface.value };
}

async function saveItem() {
  if (!canEditCurrent.value || !canSave.value) return;
  saving.value = true;
  errorMessage.value = "";
  statusMessage.value = "";
  const payload = {
    scheduled_date: form.scheduled_date,
    title: form.title.trim(),
    detail_text: form.detail_text.trim() || null,
    status: form.status,
    assigned_user_id: null,
  };
  try {
    if (form.public_id && form.revision) {
      await api.put(
        `/safety-features/team-schedule/items/${form.public_id}`,
        { ...payload, revision: form.revision },
        { headers: writeHeaders() },
      );
    } else {
      await api.post(
        "/safety-features/team-schedule/items",
        { ...payload, client_item_key: form.client_item_key },
        { headers: writeHeaders() },
      );
    }
    statusMessage.value = "팀 스케줄에 저장했습니다.";
    resetForm(form.scheduled_date);
    await loadItems();
  } catch (error) {
    errorMessage.value = apiErrorMessage(error, "일정을 저장하지 못했습니다.");
  } finally {
    saving.value = false;
  }
}

async function completeItem() {
  if (!canEditCurrent.value || !form.public_id || !form.revision) return;
  if (
    !confirmEditorTransition(
      "저장하지 않은 수정 내용은 완료 처리에 포함되지 않습니다. 변경 내용을 버리고 계속할까요?",
    )
  ) {
    return;
  }
  saving.value = true;
  errorMessage.value = "";
  try {
    await api.post(
      `/safety-features/team-schedule/items/${form.public_id}/complete`,
      { revision: form.revision },
      { headers: writeHeaders() },
    );
    statusMessage.value = "일정을 완료 처리했습니다.";
    resetForm(form.scheduled_date);
    await loadItems();
  } catch (error) {
    errorMessage.value = apiErrorMessage(error, "완료 처리하지 못했습니다.");
  } finally {
    saving.value = false;
  }
}

async function archiveItem() {
  if (!canEditCurrent.value || !form.public_id || !form.revision) return;
  if (
    !confirmEditorTransition(
      "저장하지 않은 수정 내용은 보관되지 않습니다. 변경 내용을 버리고 계속할까요?",
    )
  ) {
    return;
  }
  if (!window.confirm("이 일정을 목록에서 보관할까요? 기록은 삭제되지 않습니다.")) return;
  saving.value = true;
  errorMessage.value = "";
  try {
    await api.post(
      `/safety-features/team-schedule/items/${form.public_id}/archive`,
      { revision: form.revision },
      { headers: writeHeaders() },
    );
    statusMessage.value = "일정을 보관했습니다. 감사 기록은 유지됩니다.";
    resetForm(form.scheduled_date);
    await loadItems();
  } catch (error) {
    errorMessage.value = apiErrorMessage(error, "일정을 보관하지 못했습니다.");
  } finally {
    saving.value = false;
  }
}

async function addComment() {
  if (!canWrite.value || !form.public_id || !commentDraft.value.trim()) return;
  saving.value = true;
  errorMessage.value = "";
  try {
    await api.post(
      `/safety-features/team-schedule/items/${form.public_id}/comments`,
      { body_text: commentDraft.value.trim() },
      { headers: writeHeaders() },
    );
    commentDraft.value = "";
    await loadComments(form.public_id);
    statusMessage.value = "댓글을 등록했습니다.";
  } catch (error) {
    errorMessage.value = apiErrorMessage(error, "댓글을 등록하지 못했습니다.");
  } finally {
    saving.value = false;
  }
}

watch([year, month], () => {
  void loadItems().catch((error) => {
    errorMessage.value = apiErrorMessage(error, "일정을 불러오지 못했습니다.");
  });
});

function handleBeforeUnload(event: BeforeUnloadEvent) {
  if (!isDirty.value && !saving.value) return;
  event.preventDefault();
  event.returnValue = "";
}

onBeforeRouteLeave(() => confirmEditorTransition());

onMounted(() => {
  isMobileDevice.value = readMobileDevice();
  window.addEventListener("beforeunload", handleBeforeUnload);
  void reload();
});

onUnmounted(() => {
  window.removeEventListener("beforeunload", handleBeforeUnload);
});
</script>

<style scoped>
.team-schedule-page {
  max-width: 1480px;
  margin: 0 auto;
  color: #0f172a;
}
.page-header,
.month-nav,
.editor-title-row,
.editor-actions {
  display: flex;
  align-items: center;
}
.page-header {
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 14px;
}
.eyebrow {
  margin: 0 0 3px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}
h2,
h3,
.subtitle {
  margin: 0;
}
h2 {
  font-size: 25px;
}
.subtitle {
  margin-top: 5px;
  color: #64748b;
  font-size: 13px;
}
.member-line,
.owner-help {
  margin: 5px 0 0;
  color: #64748b;
  font-size: 11px;
}
.owner-notice {
  margin: 0 0 12px;
  padding: 9px 10px;
  border: 1px solid #d1d5db;
  border-radius: 7px;
  background: #f8fafc;
  color: #334155;
  font-size: 12px;
}
.comment-panel {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}
.comment-panel h4 {
  margin: 0 0 8px;
}
.comment-panel ul {
  display: grid;
  gap: 6px;
  margin: 0 0 8px;
  padding: 0;
  list-style: none;
}
.comment-panel li {
  padding: 7px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
}
.comment-panel li strong,
.comment-panel li span {
  display: block;
}
.comment-panel li span {
  margin-top: 3px;
  white-space: pre-wrap;
}
.comment-panel textarea {
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 6px;
  padding: 7px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  resize: vertical;
}
.comment-empty {
  color: #94a3b8;
  font-size: 12px;
}
.month-nav {
  gap: 8px;
  flex-wrap: wrap;
}
.month-nav strong {
  min-width: 110px;
  text-align: center;
}
.surface-notice,
.error-message,
.status-message {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 13px;
}
.surface-notice {
  background: #f1f5f9;
  color: #475569;
}
.mobile-notice {
  background: #eff6ff;
  color: #1d4ed8;
}
.error-message {
  background: #fef2f2;
  color: #b91c1c;
}
.status-message {
  background: #ecfdf5;
  color: #047857;
}
.workspace {
  display: grid;
  grid-template-columns: minmax(270px, 330px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.workspace--read-only {
  grid-template-columns: minmax(0, 1fr);
}
.editor-card,
.calendar-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
}
.editor-card {
  position: sticky;
  top: 12px;
  padding: 16px;
}
.editor-title-row {
  justify-content: space-between;
  margin-bottom: 14px;
}
.editor-card label {
  display: grid;
  gap: 5px;
  margin-bottom: 11px;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}
.editor-card input,
.editor-card select,
.editor-card textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 9px;
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  background: #fff;
  color: #0f172a;
  font: inherit;
  font-weight: 400;
}
.editor-card textarea {
  resize: vertical;
}
.editor-actions {
  gap: 7px;
  flex-wrap: wrap;
}
.editor-help {
  margin: 12px 0 0;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.45;
}
.calendar-card {
  min-width: 0;
  padding: 14px;
}
.weekday-row,
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 5px;
}
.weekday-row {
  margin-bottom: 5px;
}
.weekday-row span {
  padding: 5px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  text-align: center;
}
.day-cell {
  min-height: 118px;
  padding: 6px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}
.day-cell.muted {
  background: #f8fafc;
  color: #cbd5e1;
}
.day-cell.today {
  border-color: #2563eb;
  box-shadow: inset 0 0 0 1px #2563eb;
}
.day-number {
  display: block;
  margin-bottom: 5px;
  font-size: 12px;
  font-weight: 800;
}
.day-items {
  display: grid;
  gap: 4px;
}
.schedule-chip {
  min-width: 0;
  padding: 5px 6px;
  border: 0;
  border-left: 3px solid #2563eb;
  border-radius: 5px;
  background: #eff6ff;
  color: #1e3a8a;
  text-align: left;
  cursor: pointer;
}
.schedule-chip span,
.schedule-chip small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.schedule-chip span {
  font-size: 11px;
  font-weight: 750;
}
.schedule-chip small {
  margin-top: 2px;
  color: #64748b;
  font-size: 9px;
}
.schedule-chip.status-completed {
  border-left-color: #16a34a;
  background: #f0fdf4;
  color: #166534;
}
.schedule-chip.status-in_progress {
  border-left-color: #f59e0b;
  background: #fffbeb;
  color: #92400e;
}
.schedule-chip.status-on_hold {
  border-left-color: #64748b;
  background: #f8fafc;
  color: #475569;
}
.empty-state {
  padding: 36px 12px;
  color: #94a3b8;
  text-align: center;
}
.desktop-empty {
  padding-bottom: 8px;
}
.mobile-agenda {
  display: grid;
  gap: 8px;
}
.agenda-item {
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}
.agenda-summary {
  display: grid;
  grid-template-columns: 66px minmax(0, 1fr) 18px;
  gap: 9px;
  align-items: center;
  width: 100%;
  padding: 12px;
  border: 0;
  background: #fff;
  color: #0f172a;
  text-align: left;
}
.agenda-date {
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
}
.agenda-main {
  min-width: 0;
}
.agenda-main strong,
.agenda-main small {
  display: block;
}
.agenda-main strong {
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.agenda-main small {
  margin-top: 3px;
  color: #64748b;
  font-size: 11px;
}
.agenda-detail {
  padding: 0 12px 12px 87px;
  color: #475569;
  font-size: 13px;
  white-space: pre-wrap;
}
.agenda-detail p {
  margin: 0 0 8px;
}
.agenda-detail small {
  color: #94a3b8;
}
button.primary,
button.secondary,
button.complete,
button.danger-link {
  padding: 7px 10px;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
button.primary {
  border: 1px solid #2563eb;
  background: #2563eb;
  color: #fff;
}
button.secondary {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
}
button.complete {
  border: 1px solid #16a34a;
  background: #f0fdf4;
  color: #166534;
}
button.danger-link {
  border: 1px solid #fecaca;
  background: #fff;
  color: #b91c1c;
}
button.compact {
  padding: 5px 8px;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
@media (max-width: 1100px) and (min-width: 769px) {
  .workspace {
    grid-template-columns: 270px minmax(0, 1fr);
  }
  .day-cell {
    min-height: 100px;
  }
}
@media (max-width: 768px) {
  .team-schedule-page {
    padding: 0;
  }
  .page-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }
  .month-nav {
    width: 100%;
  }
  .month-nav strong {
    flex: 1;
  }
  .workspace {
    display: block;
  }
  .calendar-card {
    padding: 10px;
  }
}
</style>
