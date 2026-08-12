<template>
  <div class="feedback-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">WORKER SAFETY VOICE</p>
        <h1>근로자의견청취 관리대장</h1>
        <p>Google Form 의견을 전화번호 우선으로 현장에 배정하고, 현장 조치와 본사 검토·안전가점을 한 흐름으로 관리합니다.</p>
      </div>
      <div class="head-actions">
        <a :href="FORM_URL" target="_blank" rel="noopener noreferrer" class="btn btn-ghost">의견 제출 폼</a>
        <button class="btn btn-primary" type="button" :disabled="loading" @click="load">
          {{ loading ? "동기화 중" : "새로고침" }}
        </button>
      </div>
    </header>

    <p v-if="message" class="notice" :class="{ error: messageIsError }">{{ message }}</p>

    <section class="kpi-grid">
      <article><span>전체 의견</span><strong>{{ items.length }}</strong></article>
      <article><span>현장 조치 대기</span><strong>{{ pendingCount }}</strong></article>
      <article><span>조치 완료</span><strong>{{ doneCount }}</strong></article>
      <article><span>현장 미매칭</span><strong>{{ unmatchedCount }}</strong></article>
    </section>

    <section class="workflow-strip">
      <span>1. 폼 접수</span><i>→</i><span>2. 전화번호로 현장 배정</span><i>→</i><span>3. 현장 즉시 조치</span><i>→</i><span>4. 본사 검토·가점</span>
    </section>

    <section class="panel">
      <div class="panel-title">
        <div>
          <h2>{{ isSite ? "우리 현장 의견" : "전체 현장 의견" }}</h2>
          <p>{{ isSite ? "우리 현장에 배정된 의견만 표시됩니다." : "본사는 모든 현장의 의견과 조치 결과를 확인합니다." }}</p>
        </div>
        <select v-model="statusFilter" aria-label="상태 필터">
          <option value="ALL">전체 상태</option>
          <option value="PENDING">미접수</option>
          <option value="RECEIVED">접수</option>
          <option value="DONE">조치완료</option>
        </select>
      </div>

      <div v-if="displayItems.length" class="opinion-list">
        <article v-for="item in displayItems" :key="item.id" class="opinion-card">
          <div class="opinion-top">
            <div>
              <span class="status" :class="statusClass(item.action_status)">{{ statusLabel(item.action_status) }}</span>
              <span class="match" :class="{ bad: item.match_status !== 'matched' }">{{ matchLabel(item) }}</span>
            </div>
            <time>{{ formatDateTimeKst(item.submitted_at || item.submitted_at_raw, "-") }}</time>
          </div>

          <div class="opinion-main">
            <div class="identity">
              <strong>{{ item.worker_name || "익명" }}</strong>
              <span>{{ item.phone_masked || "전화번호 없음" }}</span>
              <span>{{ item.matched_site_name || item.submitted_site_name || "현장 미확인" }}</span>
            </div>
            <div class="content">
              <span class="type">{{ item.opinion_type || "기타 의견" }}</span>
              <p>{{ item.content || "내용 없음" }}</p>
            </div>
          </div>

          <div v-if="item.action_result" class="action-result">
            <span>현장 조치결과</span>
            <p>{{ item.action_result }}</p>
          </div>

          <div v-if="isSite" class="card-actions">
            <button v-if="item.action_status === 'PENDING'" class="btn btn-ghost" type="button" @click="receive(item.id)">접수 확인</button>
            <button v-if="item.action_status !== 'DONE'" class="btn btn-primary" type="button" @click="complete(item.id)">조치완료 기록</button>
            <span v-else class="completed-copy">조치 의무 이행 완료</span>
          </div>

          <div v-else class="hq-review">
            <div class="score-grid">
              <label>적정성<select v-model.number="scoreDrafts[item.id].appropriateness"><option v-for="n in 5" :key="n" :value="n">{{ n }}</option></select></label>
              <label>실행성<select v-model.number="scoreDrafts[item.id].actionability"><option v-for="n in 5" :key="n" :value="n">{{ n }}</option></select></label>
              <label>예방성<select v-model.number="scoreDrafts[item.id].prevention"><option v-for="n in 5" :key="n" :value="n">{{ n }}</option></select></label>
              <label class="notes">본사 메모<input v-model="scoreDrafts[item.id].notes" type="text" placeholder="부적정 의견 제외 사유 등" /></label>
            </div>
            <div class="card-actions">
              <button class="btn btn-ghost" type="button" :disabled="item.action_status !== 'DONE'" @click="score(item.id)">검토 저장</button>
              <button class="btn btn-accent" type="button" :disabled="!canAward(item)" @click="award(item.id)">
                {{ item.bonus_awarded_at ? `안전가점 +${item.bonus_points} 확정` : "안전가점 +5 확정" }}
              </button>
              <span v-if="item.score_total != null">검토점수 {{ item.score_total }}/15</span>
            </div>
          </div>
        </article>
      </div>
      <p v-else class="empty">표시할 의견이 없습니다.</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { formatDateTimeKst } from "@/utils/datetime";

interface FeedbackItem {
  id: number;
  submitted_at?: string | null;
  submitted_at_raw?: string | null;
  worker_name?: string | null;
  phone_masked?: string | null;
  opinion_type?: string | null;
  content?: string | null;
  submitted_site_name?: string | null;
  matched_site_name?: string | null;
  matched_worker_id?: number | null;
  match_status: string;
  action_status: string;
  action_result?: string | null;
  appropriateness_score?: number | null;
  actionability_score?: number | null;
  prevention_score?: number | null;
  score_total?: number | null;
  bonus_points: number;
  bonus_awarded_at?: string | null;
  notes?: string | null;
}

interface ScoreDraft { appropriateness: number; actionability: number; prevention: number; notes: string }

const FORM_URL = "https://forms.gle/U6b7dg6y29eL3kBw6";
const auth = useAuthStore();
const items = ref<FeedbackItem[]>([]);
const loading = ref(false);
const message = ref("");
const messageIsError = ref(false);
const statusFilter = ref("ALL");
const scoreDrafts = ref<Record<number, ScoreDraft>>({});
let refreshTimer: number | null = null;

const isSite = computed(() => auth.user?.role === "SITE");
const pendingCount = computed(() => items.value.filter((x) => x.action_status !== "DONE").length);
const doneCount = computed(() => items.value.filter((x) => x.action_status === "DONE").length);
const unmatchedCount = computed(() => items.value.filter((x) => x.match_status !== "matched").length);
const displayItems = computed(() => statusFilter.value === "ALL" ? items.value : items.value.filter((x) => x.action_status === statusFilter.value));

function syncScoreDrafts(rows: FeedbackItem[]) {
  for (const item of rows) {
    scoreDrafts.value[item.id] = {
      appropriateness: item.appropriateness_score || 3,
      actionability: item.actionability_score || 3,
      prevention: item.prevention_score || 3,
      notes: item.notes || "",
    };
  }
}

function errorText(error: unknown) {
  const ax = error as { response?: { data?: { detail?: unknown } }; message?: string };
  return typeof ax.response?.data?.detail === "string" ? ax.response.data.detail : (ax.message || "요청을 처리하지 못했습니다.");
}

async function load(silent = false) {
  if (!silent) loading.value = true;
  try {
    const res = await api.get<{ items: FeedbackItem[]; sync?: { error?: string | null } }>("/worker-feedback/responses", { params: { limit: 500 } });
    items.value = res.data.items || [];
    syncScoreDrafts(items.value);
    if (res.data.sync?.error) {
      message.value = `Google Form 동기화 지연: ${res.data.sync.error}`;
      messageIsError.value = true;
    } else if (!silent) {
      message.value = "Google Form 응답과 관리대장을 동기화했습니다.";
      messageIsError.value = false;
    }
  } catch (error) {
    message.value = errorText(error);
    messageIsError.value = true;
  } finally {
    loading.value = false;
  }
}

async function run(success: string, action: () => Promise<unknown>) {
  try {
    await action();
    message.value = success;
    messageIsError.value = false;
    await load(true);
  } catch (error) {
    message.value = errorText(error);
    messageIsError.value = true;
  }
}

function receive(id: number) { return run("의견을 접수했습니다.", () => api.post(`/worker-feedback/${id}/receive`)); }
function complete(id: number) {
  const result = window.prompt("현장에서 실시한 조치 결과를 입력하세요.", "");
  if (!result?.trim()) return;
  return run("현장 조치완료를 기록했습니다.", () => api.post(`/worker-feedback/${id}/complete`, { action_result: result.trim() }));
}
function score(id: number) {
  const d = scoreDrafts.value[id];
  return run("본사 검토를 저장했습니다.", () => api.patch(`/worker-feedback/${id}/score`, {
    appropriateness_score: d.appropriateness,
    actionability_score: d.actionability,
    prevention_score: d.prevention,
    notes: d.notes,
  }));
}
function award(id: number) { return run("기능인 안전가점 5점을 확정했습니다.", () => api.post(`/worker-feedback/${id}/award`, { bonus_points: 5 })); }
function canAward(item: FeedbackItem) { return item.action_status === "DONE" && item.score_total != null && !!item.matched_worker_id && !item.bonus_awarded_at; }
function statusLabel(v: string) { return v === "DONE" ? "조치완료" : v === "RECEIVED" ? "접수" : "미접수"; }
function statusClass(v: string) { return v === "DONE" ? "done" : v === "RECEIVED" ? "received" : "pending"; }
function matchLabel(item: FeedbackItem) { return item.match_status === "matched" ? "현장 배정" : item.match_status === "ambiguous" ? "현장 중복 확인" : "현장 미확인"; }

onMounted(async () => {
  await load();
  refreshTimer = window.setInterval(() => void load(true), 30_000);
});
onUnmounted(() => { if (refreshTimer) window.clearInterval(refreshTimer); });
</script>

<style scoped>
.feedback-page { display: grid; gap: 18px; color: #17221c; }
.page-head { display: flex; justify-content: space-between; gap: 24px; padding: 24px; border-radius: 20px; background: linear-gradient(120deg, #f2f7ee 0%, #e4f0e8 55%, #d7e9e5 100%); border: 1px solid #c7d9cc; }
.eyebrow { margin: 0 0 6px; color: #557362; font-size: 11px; font-weight: 800; letter-spacing: .16em; }
h1 { margin: 0; font-size: 26px; font-family: "Noto Serif KR", Georgia, serif; }
.page-head p:last-child, .panel-title p { margin: 7px 0 0; color: #5d6c63; font-size: 13px; }
.head-actions, .card-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.btn { border: 1px solid transparent; border-radius: 10px; padding: 9px 13px; font: inherit; font-size: 13px; font-weight: 700; cursor: pointer; text-decoration: none; }
.btn:disabled { opacity: .45; cursor: not-allowed; }
.btn-primary { background: #1f5b42; color: white; }
.btn-ghost { background: white; border-color: #b9cabf; color: #274a38; }
.btn-accent { background: #d97706; color: white; }
.notice { margin: 0; padding: 11px 14px; border-radius: 10px; background: #edf8ef; color: #24613d; font-size: 13px; }
.notice.error { background: #fff1ed; color: #9a3412; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.kpi-grid article { display: flex; justify-content: space-between; align-items: end; padding: 16px; background: white; border: 1px solid #dce5df; border-radius: 14px; }
.kpi-grid span { color: #68776e; font-size: 12px; }
.kpi-grid strong { font-size: 25px; }
.workflow-strip { display: flex; align-items: center; justify-content: center; gap: 14px; padding: 12px; border-radius: 12px; background: #243a30; color: #f5f8f6; font-size: 12px; font-weight: 700; }
.workflow-strip i { color: #9bb6a6; font-style: normal; }
.panel { padding: 18px; background: #fff; border: 1px solid #dce5df; border-radius: 18px; }
.panel-title { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 14px; }
.panel-title h2 { margin: 0; font-size: 19px; }
.panel-title select, .score-grid select, .score-grid input { border: 1px solid #cbd8d0; border-radius: 8px; padding: 7px 9px; background: white; }
.opinion-list { display: grid; gap: 12px; }
.opinion-card { padding: 16px; border: 1px solid #dce5df; border-left: 4px solid #6b8f79; border-radius: 12px; background: #fbfdfb; }
.opinion-top, .opinion-main { display: flex; justify-content: space-between; gap: 18px; }
.opinion-top time { color: #718077; font-size: 12px; }
.status, .match, .type { display: inline-flex; padding: 4px 8px; border-radius: 999px; font-size: 11px; font-weight: 800; }
.status.pending { background: #fff0d5; color: #945b00; }
.status.received { background: #e1efff; color: #1e5d91; }
.status.done { background: #dff3e4; color: #24613d; }
.match { margin-left: 6px; background: #e8eeea; color: #526158; }
.match.bad { background: #ffe7e2; color: #9a3412; }
.opinion-main { margin-top: 14px; }
.identity { width: 180px; flex: 0 0 180px; display: grid; align-content: start; gap: 3px; }
.identity span { color: #66766c; font-size: 12px; }
.content { flex: 1; }
.content p, .action-result p { margin: 7px 0 0; line-height: 1.55; white-space: pre-wrap; }
.type { background: #eef3ef; color: #3d5a49; }
.action-result { margin-top: 13px; padding: 12px; border-radius: 9px; background: #f0f6f2; }
.action-result span { color: #52705e; font-size: 11px; font-weight: 800; }
.card-actions, .hq-review { margin-top: 14px; padding-top: 13px; border-top: 1px solid #e2e9e4; }
.completed-copy { color: #287044; font-size: 12px; font-weight: 800; }
.score-grid { display: grid; grid-template-columns: 100px 100px 100px minmax(180px, 1fr); gap: 8px; }
.score-grid label { display: grid; gap: 4px; color: #5e6f65; font-size: 11px; font-weight: 700; }
.empty { padding: 42px; text-align: center; color: #7b8980; }
@media (max-width: 900px) {
  .page-head, .opinion-main { flex-direction: column; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .workflow-strip { overflow-x: auto; justify-content: flex-start; white-space: nowrap; }
  .identity { width: auto; flex-basis: auto; }
  .score-grid { grid-template-columns: repeat(3, 1fr); }
  .score-grid .notes { grid-column: 1 / -1; }
}
@media (max-width: 560px) {
  .kpi-grid { grid-template-columns: 1fr; }
  .page-head { padding: 18px; }
  .panel { padding: 12px; }
  .panel-title { align-items: flex-start; flex-direction: column; }
}
</style>
