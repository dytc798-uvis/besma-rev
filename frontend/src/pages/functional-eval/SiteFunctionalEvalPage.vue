<template>
  <div class="fe-page">
    <div class="page-head">
      <div class="page-head-text">
        <h1 class="page-title">기능인 인정제 평가</h1>
        <p class="page-sub">
          <span v-if="evaluator" :class="['evaluator-badge', evaluatorBadgeClass]">{{ evaluatorHeadline }}</span>
          마감일 <strong>{{ period?.deadline_date || "—" }}</strong>
          <span v-if="period?.last_attendance_date"> · 출역 {{ period.last_attendance_date }} ({{ workers.length }}명)</span>
        <button
          v-if="!period?.is_closed"
          class="incomplete-count"
          type="button"
          :disabled="!canStartFromIncomplete"
          @click="startEvaluationFromIncomplete"
        >
          미평가 {{ incompleteCount }}명
        </button>
          <span v-if="period?.is_closed" class="badge closed">마감</span>
          <span v-else class="badge open">진행</span>
        </p>
        <p v-if="evaluatorHint" class="evaluator-hint">{{ evaluatorHint }}</p>
        <p v-if="attendanceMessage" class="attendance-warn">{{ attendanceMessage }}</p>
      </div>
      <div class="page-head-actions">
      <button
        v-if="!evaluator || evaluator.role === 'MANAGER'"
        class="btn-export stitch-btn-primary"
        type="button"
        :disabled="exportingGrade"
        @click="downloadSiteGradeWorkbook"
      >
        {{ exportingGrade ? "출력 중…" : "현장별 기능인등급 출력" }}
      </button>
      <button class="btn-refresh stitch-btn-secondary" type="button" @click="load">새로고침</button>
      </div>
    </div>

        <nav class="fe-tabs" aria-label="기능인 인정제 평가">
      <template v-if="mainView === 'evaluate'">
        <button type="button" class="fe-tab fe-tab-back" @click="goToRoster">← 현황</button>
        <button type="button" class="fe-tab" :class="{ active: activeTab === 'functional' }" @click="activeTab = 'functional'">
          2-1 기능
        </button>
        <button type="button" class="fe-tab" :class="{ active: activeTab === 'safety' }" @click="activeTab = 'safety'">
          2-2 안전·제재
        </button>
      </template>
      <template v-else>
        <button type="button" class="fe-tab active">
          등급 현황
        </button>
      </template>
    </nav>

    <!-- 첫 화면: 근로자별 현재 등급 -->
    <section v-if="mainView === 'roster'" class="panel roster-panel">
      <div class="roster-toolbar">
        <button
          class="stitch-btn-primary btn-start-eval"
          type="button"
          :disabled="Boolean(period?.is_closed) || !rosterSource.length"
          @click="startEvaluation()"
        >
          평가 시작
        </button>
      </div>
      <p class="roster-desc">{{ rosterDescription }}</p>

      <div v-if="isManager && approval" class="approval-panel">
        <div class="approval-stats">
          <span>전체 {{ approval.site_complete_workers }}/{{ approval.site_total_workers }}명 완료</span>
          <span v-if="evaluator?.team_split_active"> · 직영 {{ approval.direct_complete }}/{{ approval.direct_total }}</span>
          <span v-if="approval.team_total"> · 팀원 {{ approval.team_complete }}/{{ approval.team_total }}</span>
        </div>
        <p class="approval-status">{{ approval.status_label }}</p>
        <button
          v-if="approval.can_submit_site_approval"
          class="stitch-btn-primary btn-approve-site"
          type="button"
          :disabled="submittingApproval || Boolean(period?.is_closed)"
          @click="submitSiteApproval"
        >
          {{ submittingApproval ? "제출 중…" : "현장 전체 승인" }}
        </button>
      </div>

      <div class="table-wrap roster-table-wrap">
        <table class="data-table roster-table">
          <thead>
            <tr>
              <th>번호</th>
              <th>성명</th>
              <th v-if="isManager && evaluator?.team_split_active">구분</th>
              <th>기능 (2-1)</th>
              <th>안전·제재 (2-2)</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(w, idx) in filteredWorkers" :key="w.id" :class="workerRowHighlightClass(w)">
              <td>{{ idx + 1 }}</td>
              <td>{{ w.name }}</td>
              <td v-if="isManager && evaluator?.team_split_active">{{ assignmentLabel(w) }}</td>
              <td>
                <span :class="gradeDisplayClass(w.functional_assessment)">{{ gradeDisplayLabel(w.functional_assessment) }}</span>
              </td>
              <td class="safety-sanction-cell">
                <span :class="safetySanctionCell(w).safetyClass">{{ safetySanctionCell(w).safetyLabel }}</span>
                <span
                  v-if="safetySanctionCell(w).subLabel"
                  :class="safetySanctionCell(w).subClass"
                >{{ safetySanctionCell(w).subLabel }}</span>
              </td>
              <td class="actions-cell">
                <button
                  class="status-pill status-pill-link"
                  :class="rosterStatusClass(w)"
                  type="button"
                  :disabled="!canEvaluateWorker(w) || rosterStatusLabel(w) === '평가완료'"
                  @click="onRosterStatusClick(w)"
                >
                  {{ rosterStatusLabel(w) }}
                </button>
                <button
                  v-if="canEvaluateWorker(w)"
                  class="link-btn"
                  type="button"
                  @click="startEvaluation(w)"
                >
                  평가
                </button>
                <span v-else-if="evaluationLocked" class="muted-action">승인 중</span>
                <button
                  v-if="canOpenHistory(w)"
                  class="link-btn"
                  type="button"
                  @click="openHistory(w)"
                >
                  이력
                </button>
                <button
                  v-if="canRegisterSanction(w)"
                  class="link-btn"
                  type="button"
                  @click="openSanction(w)"
                >
                  제재
                </button>
              </td>
            </tr>
            <tr v-if="!filteredWorkers.length">
              <td :colspan="rosterColspan" class="empty-cell">검색 결과가 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <FunctionalEvalWorkspace
      v-if="mainView === 'evaluate' && evalCriteria.length"
      :key="`${evalSessionKey}-${activeTab}`"
      :workers="rosterSource"
      :eval-type="currentEvalType"
      :title="evalTabTitle"
      :criteria="evalCriteria"
      :period-closed="Boolean(period?.is_closed)"
      :focus-worker-id="focusWorkerId"
      :auto-pick-on-mount="false"
      :grouped-violations="groupedViolations"
      :sanction-prompt-message="sanctionPromptMessage"
      :default-violation-code="form.violation_code"
      :reload="load"
      @request-safety="onRequestSafety"
      @safety-saved="onSafetySaved"
      @sanction-saved="sanctionPromptMessage = ''"
      @open-history="openHistoryById"
    />

    <!-- 제재·이력 모달 (모바일 바텀시트 / 데스크톱 중앙 모달) -->
    <Teleport to="body">
      <div
        v-if="selectedWorker || historyWorker"
        class="fe-overlay-backdrop"
        aria-hidden="true"
        @click="closePanels"
      />
      <section
        v-if="selectedWorker"
        class="panel sanction-form fe-dialog"
        :class="dialogShellClass"
        role="dialog"
        aria-modal="true"
        :aria-label="`${selectedWorker.name} 제재 등록`"
        @click.stop
      >
        <div v-if="isMobileViewport" class="fe-sheet-handle" aria-hidden="true" />
        <div class="dialog-head">
          <h2>{{ selectedWorker.name }} — 위반·제재</h2>
          <button class="link-btn dialog-close" type="button" aria-label="닫기" @click="closeForm">✕</button>
        </div>
        <p v-if="sanctionPromptMessage" class="sanction-hint">{{ sanctionPromptMessage }}</p>
        <label class="field">
          <span class="field-label">위반 항목</span>
          <select v-model="form.violation_code" class="field-control">
            <optgroup v-for="group in groupedViolations" :key="group.category" :label="group.label">
              <option v-for="item in group.items" :key="item.code" :value="item.code">{{ item.label }}</option>
            </optgroup>
          </select>
        </label>
        <label class="field">
          <span class="field-label">비고</span>
          <textarea v-model="form.note" class="field-control" rows="3" placeholder="위반 상황 (선택)" />
        </label>
        <div class="actions" :class="{ 'actions-sticky': isMobileViewport }">
          <button class="stitch-btn-secondary touch-btn" type="button" @click="closeForm">취소</button>
          <button
            class="stitch-btn-primary touch-btn"
            type="button"
            :disabled="!form.violation_code || saving || period?.is_closed"
            @click="requestSubmitSanction"
          >
            {{ saving ? "등록 중…" : "제재 등록" }}
          </button>
        </div>
        <p v-if="error" class="error">{{ error }}</p>
      </section>

      <section
        v-else-if="historyWorker"
        class="panel history-panel fe-dialog"
        :class="dialogShellClass"
        role="dialog"
        aria-modal="true"
        :aria-label="`${historyWorker.name} 이력`"
        @click.stop
      >
        <div v-if="isMobileViewport" class="fe-sheet-handle" aria-hidden="true" />
        <div class="dialog-head history-head">
          <h2>{{ historyWorker.name }} — 평가·제재 이력</h2>
          <button class="dialog-close" type="button" aria-label="닫기" @click="closeHistory">✕</button>
        </div>
        <p v-if="!historyData?.history_visible" class="warn">{{ historyData?.message }}</p>
        <div v-else class="history-sections">
          <section v-if="allHistoryAssessments.length" class="history-block">
            <h3>과거 평가 등급</h3>
            <ul class="history-list">
              <li v-for="(a, i) in allHistoryAssessments" :key="`a-${i}`">
                <span v-if="a.from_prior_period" class="tag">이전</span>
                {{ a.period_title || `기간 ${a.period_id}` }}
                — 기능 {{ gradeDisplayLabel(a.functional_assessment) }} · 안전 {{ gradeDisplayLabel(a.safety_assessment) }}
              </li>
            </ul>
          </section>
          <section class="history-block">
            <h3>제재 이력</h3>
            <ul class="history-list">
              <li v-for="s in allHistorySanctions" :key="`${s.id}-h`">
                <span v-if="s.from_prior_period" class="tag">이전</span>
                {{ s.violation_label }} → {{ s.sanction_result_label }} ({{ s.strike_number }}차)
                <span class="meta">{{ formatDate(s.created_at) }}</span>
              </li>
              <li v-if="!allHistorySanctions.length">제재 이력 없음</li>
            </ul>
          </section>
        </div>
        <div class="mileage-box">
          <h3>마일리지 (운영 준비)</h3>
          <p>{{ historyData?.mileage?.message }}</p>
          <p class="meta">적립 예정: {{ historyData?.mileage?.points ?? 0 }}점</p>
        </div>
      </section>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import FunctionalEvalWorkspace from "@/components/functional-eval/FunctionalEvalWorkspace.vue";
import type { Criterion } from "@/components/functional-eval/EvalAssessmentSheet.vue";
import { useMobileViewport } from "@/composables/useMobileViewport";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/services/api";
import {
  countIncompleteWorkers,
  gradeDisplayClass,
  gradeDisplayLabel,
  isEvalIncomplete,
  isFunctionalComplete,
  isSafetyComplete,
  isFullyComplete,
  needsSanctionPrompt,
  safetySanctionDisplay,
  workerRowHighlightClass,
} from "@/utils/functionalEvalCompletion";

type MainView = "roster" | "evaluate";
type EvalTab = "functional" | "safety";
type EvalType = "FUNCTIONAL" | "SAFETY";

interface AssessmentBrief {
  scores: Record<string, string>;
  total_score: number;
  max_score: number;
  grade_code: string;
  grade_label: string;
  is_complete: boolean;
}

interface EvalCatalogBlock {
  title: string;
  criteria: Criterion[];
  max_score: number;
}

interface EvaluatorSession {
  role: "MANAGER" | "TEAM_LEADER";
  role_label: string;
  eval_scope_label?: string;
  login_id: string;
  display_name: string;
  site_code: string;
  site_alias: string;
  manager_name: string;
  assigned_worker_count: number;
  site_worker_count: number;
  team_split_active: boolean;
  split_threshold: number;
}

interface ApprovalPayload {
  status: string;
  status_label: string;
  site_total_workers: number;
  site_complete_workers: number;
  direct_total: number;
  direct_complete: number;
  team_total: number;
  team_complete: number;
  incomplete_count: number;
  can_submit_site_approval: boolean;
  evaluation_editable: boolean;
  reject_note?: string | null;
}

interface Period {
  id: number;
  deadline_date: string;
  is_closed: boolean;
  last_attendance_date?: string | null;
  attendance_row_count?: number;
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
  eval_assignment?: "DIRECT" | "TEAM";
  sanction_status: string;
  sanction_status_label: string;
  is_permanently_expelled: boolean;
  history_visible: boolean;
  functional_assessment?: AssessmentBrief | null;
  safety_assessment?: AssessmentBrief | null;
}

interface AssessmentHistoryRow {
  period_id: number;
  period_title?: string;
  functional_assessment?: AssessmentBrief | null;
  safety_assessment?: AssessmentBrief | null;
  from_prior_period?: boolean;
}

interface SanctionRow {
  id: number;
  violation_label: string;
  sanction_result_label: string;
  strike_number: number;
  created_at: string;
  from_prior_period?: boolean;
}

const { isMobileViewport } = useMobileViewport();
const route = useRoute();
const router = useRouter();

const mainView = computed<MainView>(() =>
  route.name === "site-functional-eval-evaluate" ? "evaluate" : "roster",
);
const activeEvalStatus = computed(() => {
  const q = typeof route.query.eval_status === "string" ? route.query.eval_status : "";
  if (q === "진행중" || q === "평가완료") return q;
  return "미평가";
});

const activeTab = ref<EvalTab>("functional");
const focusWorkerId = ref<number | null>(null);
const evalSessionKey = ref(0);
const sanctionPromptMessage = ref("");
const evalCatalog = ref<{ FUNCTIONAL: EvalCatalogBlock; SAFETY: EvalCatalogBlock } | null>(null);
const period = ref<Period | null>(null);
const evaluator = ref<EvaluatorSession | null>(null);
const attendanceMessage = ref("");
const workers = ref<Worker[]>([]);
const siteOverview = ref<Worker[]>([]);
const approval = ref<ApprovalPayload | null>(null);
const submittingApproval = ref(false);
const violations = ref<ViolationItem[]>([]);
const selectedWorker = ref<Worker | null>(null);
const historyWorker = ref<Worker | null>(null);
const historyData = ref<{
  history_visible: boolean;
  message?: string;
  sanctions: SanctionRow[];
  prior_sanctions: SanctionRow[];
  prior_assessments?: AssessmentHistoryRow[];
  mileage: { message?: string; points?: number };
} | null>(null);
const saving = ref(false);
const exportingGrade = ref(false);
const error = ref("");
const form = reactive({ violation_code: "", note: "" });

const currentEvalType = computed<EvalType>(() => (activeTab.value === "safety" ? "SAFETY" : "FUNCTIONAL"));

const evalTabTitle = computed(() => {
  const block = evalCatalog.value?.[currentEvalType.value];
  return block?.title || (activeTab.value === "safety" ? "2-2 안전·제재" : "2-1 기능인정제 평가");
});

const evalCriteria = computed(() => evalCatalog.value?.[currentEvalType.value]?.criteria || []);

const incompleteCount = computed(() =>
  approval.value?.incomplete_count ?? countIncompleteWorkers(rosterSource.value),
);

const evaluableIncompleteCount = computed(() => rosterSource.value.filter(isEvalIncomplete).length);

const canStartFromIncomplete = computed(() =>
  !Boolean(period?.value?.is_closed)
  && evaluableIncompleteCount.value > 0,
);


const isManager = computed(() => evaluator.value?.role === "MANAGER");

const rosterSource = computed(() =>
  isManager.value && siteOverview.value.length ? siteOverview.value : workers.value,
);

const evaluationLocked = computed(() => approval.value?.evaluation_editable === false);

const evaluatorHeadline = computed(() => {
  if (!evaluator.value) return "";
  if (evaluator.value.eval_scope_label) return `${evaluator.value.role_label} · ${evaluator.value.eval_scope_label}`;
  if (evaluator.value.role === "TEAM_LEADER") {
    return `팀장 · 담당 ${evaluator.value.assigned_worker_count}명`;
  }
  return "소장 평가";
});

const evaluatorBadgeClass = computed(() =>
  evaluator.value?.role === "TEAM_LEADER" ? "evaluator-badge--leader" : "evaluator-badge--manager",
);

const evaluatorHint = computed(() => {
  if (approval.value?.status_label && approval.value.status !== "IN_PROGRESS") {
    return approval.value.status_label + (approval.value.reject_note ? ` — ${approval.value.reject_note}` : "");
  }
  if (!evaluator.value) return "";
  if (evaluator.value.role === "TEAM_LEADER") {
    return "담당 팀원만 평가할 수 있습니다. 소장이 현장 전체를 승인한 뒤 본사·대표 승인이 이어집니다.";
  }
  if (evaluator.value.team_split_active) {
    return `출역 ${evaluator.value.split_threshold}명 초과: 직영은 소장, 팀원은 팀장이 평가합니다. 전원 완료 후 소장이 현장 전체를 승인하세요.`;
  }
  return "10명 이하 현장은 소장이 전원 평가합니다. 완료 후 소장 승인 → 안전보건실 → 대표이사 순으로 확정됩니다.";
});

const rosterDescription = computed(() => evaluatorHint.value);

const rosterColspan = computed(() => (isManager.value && evaluator.value?.team_split_active ? 6 : 5));

const filteredWorkers = computed(() => {
  const list =
    route.name === "site-functional-eval-evaluate"
      ? rosterSource.value.filter((w) => workerEvalStatus(w) === activeEvalStatus.value)
      : rosterSource.value;
  return [...list].sort((a, b) => a.name.localeCompare(b.name, "ko"));
});

function assignmentLabel(w: Worker): string {
  if (isManager.value && !evaluator.value?.team_split_active) return "직영";
  return w.eval_assignment === "TEAM" ? "팀원" : "직영";
}

function canEvaluateWorker(w: Worker): boolean {
  return !period.value?.is_closed;
}

function startEvaluationFromIncomplete() {
  if (!canStartFromIncomplete.value) return;
  const target = rosterSource.value.find(isEvalIncomplete);
  if (!target) return;
  startEvaluation(target);
}

function canOpenHistory(w: Worker): boolean {
  if (isManager.value) {
    if (evaluator.value?.team_split_active) {
      return canEvaluateWorker(w);
    }
    return true;
  }
  return canEvaluateWorker(w);
}

function canRegisterSanction(w: Worker): boolean {
  return !period.value?.is_closed && !w.is_permanently_expelled && (needsSanctionPrompt(w) || isFullyComplete(w));
}

function safetySanctionCell(w: Worker) {
  return safetySanctionDisplay(w);
}

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

const allHistoryAssessments = computed(() => {
  if (!historyData.value?.history_visible) return [];
  return historyData.value.prior_assessments || [];
});

const dialogShellClass = computed(() =>
  isMobileViewport.value ? "fe-sheet fe-sheet-open" : "fe-modal-panel",
);

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

function closePanels() {
  closeForm();
  closeHistory();
}

function selectedViolationLabel(): string {
  const item = violations.value.find((v) => v.code === form.violation_code);
  return item?.label || "선택한 위반";
}

function requestSubmitSanction() {
  if (!selectedWorker.value || !form.violation_code) return;
  const ok = window.confirm(
    `${selectedWorker.value.name} 근로자\n위반: ${selectedViolationLabel()}\n\n제재를 등록하시겠습니까?`,
  );
  if (ok) submitSanction();
}

function workerEvalStatus(w: Worker): string {
  if (isFullyComplete(w)) return "평가완료";
  if (isFunctionalComplete(w) || isSafetyComplete(w)) return "진행중";
  return "미평가";
}

function rosterStatusLabel(w: Worker): string {
  return workerEvalStatus(w);
}

function rosterStatusClass(w: Worker): string {
  if (workerEvalStatus(w) === "평가완료") return "done";
  if (workerEvalStatus(w) === "진행중") return "normal";
  return "pending";
}

function goToRoster() {
  router.push({ name: "site-functional-eval" });
  focusWorkerId.value = null;
}

function startEvaluation(worker?: Worker) {
  const target = (() => {
    if (worker) return worker;
    const firstIncomplete = rosterSource.value.find(isEvalIncomplete);
    if (firstIncomplete) return firstIncomplete;
    return rosterSource.value[0] ?? null;
  })();
  if (!target) return;

  evalSessionKey.value += 1;
  focusWorkerId.value = target.id;
  activeTab.value = isFunctionalComplete(target) ? "safety" : "functional";
  const nextRoute = {
    name: "site-functional-eval-evaluate" as const,
    query: { eval_status: workerEvalStatus(target) },
  };

  if (route.name === "site-functional-eval-evaluate") {
    void router.replace(nextRoute);
    return;
  }
  void router.push(nextRoute);
}

function onRosterStatusClick(w: Worker) {
  if (!canEvaluateWorker(w)) return;
  if (workerEvalStatus(w) === "평가완료") return;
  startEvaluation(w);
}

function onSafetySaved(worker: Worker) {
  if (!needsSanctionPrompt(worker)) return;
  const f = gradeDisplayLabel(worker.functional_assessment);
  const s = gradeDisplayLabel(worker.safety_assessment);
  sanctionPromptMessage.value = `기능 ${f} · 안전 ${s} — 만점(S) 미달로 제재 등록이 필요합니다.`;
  focusWorkerId.value = worker.id;
  activeTab.value = "safety";
  if (isMobileViewport.value) {
    openSanction(worker);
  }
}

function onRequestSafety(workerId: number) {
  focusWorkerId.value = workerId;
  activeTab.value = "safety";
}

watch(activeTab, () => {
  closeForm();
  closeHistory();
});

watch(mainView, (view) => {
  if (view === "roster") {
    sanctionPromptMessage.value = "";
  }
});

function openHistoryById(workerId: number) {
  const worker = rosterSource.value.find((w) => w.id === workerId);
  if (worker) openHistory(worker);
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
  attendanceMessage.value = "";
  const res = await api.get("/functional-eval/my-site/workers");
  period.value = res.data.period;
  workers.value = res.data.items || [];
  siteOverview.value = res.data.site_overview || [];
  approval.value = res.data.approval || null;
  evaluator.value = res.data.evaluator || null;
  attendanceMessage.value = res.data.attendance_message || "";
}

async function submitSiteApproval() {
  if (!approval.value?.can_submit_site_approval) return;
  const ok = window.confirm("현장 전체 평가를 승인하고 안전보건실 검토로 제출하시겠습니까?");
  if (!ok) return;
  submittingApproval.value = true;
  error.value = "";
  try {
    await api.post("/functional-eval/my-site/approval/submit");
    await load();
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof msg === "string" ? msg : "현장 승인에 실패했습니다.";
  } finally {
    submittingApproval.value = false;
  }
}

function siteGradeWorkbookFilename() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `현장별 기능인등급-${y}${m}${day}.xlsx`;
}

async function downloadSiteGradeWorkbook() {
  exportingGrade.value = true;
  error.value = "";
  try {
    const res = await api.get("/functional-eval/my-site/export/site-grade-workbook", { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = siteGradeWorkbookFilename();
    a.click();
    URL.revokeObjectURL(url);
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof msg === "string" ? msg : "엑셀 출력에 실패했습니다.";
  } finally {
    exportingGrade.value = false;
  }
}

async function openHistory(worker: Worker) {
  selectedWorker.value = null;
  error.value = "";
  historyWorker.value = worker;
  historyData.value = null;
  document.body.classList.add("fe-sheet-open-body");
  try {
    const res = await api.get(`/functional-eval/workers/${worker.id}/history`);
    historyData.value = res.data;
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    historyData.value = {
      history_visible: false,
      message: typeof msg === "string" ? msg : "이력을 불러오지 못했습니다.",
      sanctions: [],
      prior_sanctions: [],
      prior_assessments: [],
      mileage: {},
    };
  }
}

function openSanction(worker: Worker) {
  historyWorker.value = null;
  historyData.value = null;
  selectedWorker.value = worker;
  form.note = "";
  error.value = "";
  document.body.classList.add("fe-sheet-open-body");
}

function closeForm() {
  selectedWorker.value = null;
  error.value = "";
  sanctionPromptMessage.value = "";
  document.body.classList.remove("fe-sheet-open-body");
}

function closeHistory() {
  historyWorker.value = null;
  historyData.value = null;
  error.value = "";
  document.body.classList.remove("fe-sheet-open-body");
}

function sanctionErrorMessage(detail: unknown): string {
  if (typeof detail !== "string") return "제재 등록에 실패했습니다.";
  if (detail === "WORKER_NOT_ON_ATTENDANCE" || detail.includes("출역")) {
    return "당일 출역 명단에 없는 근로자입니다. 출역일보 반영 후 다시 시도하세요.";
  }
  if (detail === "NO_ATTENDANCE_UPLOAD") {
    return "출역일보가 반영되지 않았습니다. 본사에 업로드 요청 후 다시 시도하세요.";
  }
  if (detail === "PERIOD_CLOSED" || detail.includes("마감")) {
    return "마감일이 지나 제재를 등록할 수 없습니다.";
  }
  return detail;
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
    sanctionPromptMessage.value = "";
    closeForm();
    await load();
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = sanctionErrorMessage(msg);
  } finally {
    saving.value = false;
  }
}

async function loadEvalCatalog() {
  const res = await api.get("/functional-eval/eval-catalog");
  evalCatalog.value = res.data;
}

onMounted(async () => {
  await Promise.all([loadCatalog(), loadEvalCatalog(), load()]);
});
</script>

<style scoped>
.attendance-warn {
  margin: 8px 0 0;
  padding: 10px 12px;
  background: #fff7ed;
  border: 1px solid #fdba74;
  border-radius: 8px;
  color: #9a3412;
  font-size: 14px;
}

.fe-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.page-head-text {
  min-width: 0;
}

.page-title {
  margin: 0;
  font-size: 1.25rem;
}

.page-sub {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.badge {
  margin-left: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  vertical-align: middle;
}

.badge.open {
  background: #dcfce7;
  color: #166534;
}

.badge.closed {
  background: #fee2e2;
  color: #991b1b;
}

.incomplete-count {
  margin-left: 10px;
  font-size: 13px;
  font-weight: 600;
  color: #b45309;
  border: none;
  padding: 0;
  background: transparent;
  cursor: pointer;
  text-decoration: underline;
  line-height: 1.2;
}

.incomplete-count:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  text-decoration: none;
}

.evaluator-badge {
  display: inline-block;
  margin-right: 8px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  vertical-align: middle;
}

.evaluator-badge--manager {
  background: #dbeafe;
  color: #1d4ed8;
}

.evaluator-badge--leader {
  background: #e0e7ff;
  color: #4338ca;
}

.evaluator-hint {
  margin: 8px 0 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.45;
}

.page-head-actions {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-refresh,
.btn-export {
  flex-shrink: 0;
}

.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px;
}

.field {
  display: block;
  margin-top: 12px;
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 6px;
}

.field-control {
  width: 100%;
  box-sizing: border-box;
  font-size: 16px;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
}

select.field-control {
  min-height: 48px;
}

textarea.field-control {
  resize: vertical;
  min-height: 80px;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.actions-sticky {
  position: sticky;
  bottom: 0;
  padding-bottom: env(safe-area-inset-bottom, 0);
  background: linear-gradient(transparent, #fff 12px);
}

.touch-btn {
  flex: 1;
  min-height: 48px;
  font-size: 15px;
}

.touch-btn-inline {
  min-height: 44px;
  padding: 8px 12px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  border-bottom: 1px solid #e5e7eb;
  padding: 10px 8px;
  text-align: left;
}

.actions-cell {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.status-pill {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.status-pill-link {
  border: none;
  background: transparent;
  cursor: pointer;
}

.status-pill-link:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.status-pill.danger {
  background: #fee2e2;
  color: #991b1b;
}

.status-pill.warn {
  background: #fef3c7;
  color: #92400e;
}

.status-pill.normal {
  background: #f1f5f9;
  color: #475569;
}

.status-pill.done {
  background: #dcfce7;
  color: #166534;
}

.status-pill.pending {
  background: #fef3c7;
  color: #92400e;
}

.fe-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.fe-tab {
  flex: 1;
  min-width: 100px;
  min-height: 44px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  color: #334155;
}

.fe-tab.active {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.fe-tab-back {
  flex: 0 0 auto;
  min-width: auto;
  padding: 0 14px;
  background: #f8fafc;
}

.roster-table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.roster-panel {
  padding: 16px;
}

.roster-toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.roster-search {
  flex: 1;
  min-width: 160px;
}

.btn-start-eval {
  min-height: 44px;
  white-space: nowrap;
}

.roster-table-wrap .data-table tbody tr.row-highlight--alert {
  background: #fef2f2;
}

.roster-table-wrap .data-table tbody tr.row-highlight--alert:hover {
  background: #fee2e2;
}

.history-sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.history-block h3 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #334155;
}

.roster-desc {
  margin: 10px 0 14px;
  font-size: 13px;
  color: #64748b;
}

.approval-panel {
  margin-bottom: 14px;
  padding: 12px 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.approval-stats {
  font-size: 13px;
  color: #334155;
  font-weight: 600;
}

.approval-status {
  margin: 8px 0 10px;
  font-size: 13px;
  color: #64748b;
}

.btn-approve-site {
  min-height: 44px;
}

.muted-action {
  font-size: 12px;
  color: #94a3b8;
}

.safety-sanction-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.roster-table .grade-pill {
  display: inline-block;
  min-width: 28px;
  text-align: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}

.grade-pill--pending {
  background: #fef3c7;
  color: #92400e;
}

.grade-pill--s {
  background: #dcfce7;
  color: #166534;
}

.grade-pill--a {
  background: #dbeafe;
  color: #1d4ed8;
}

.grade-pill--b {
  background: #e0e7ff;
  color: #4338ca;
}

.grade-pill--c {
  background: #ffedd5;
  color: #c2410c;
}

.grade-pill--d {
  background: #fee2e2;
  color: #991b1b;
}

.roster-grades {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.roster-grades .grade-pill {
  font-size: 12px;
  padding: 3px 8px;
}

.sanction-hint {
  margin: 8px 0 0;
  padding: 10px 12px;
  background: #fff7ed;
  border: 1px solid #fdba74;
  border-radius: 8px;
  color: #9a3412;
  font-size: 13px;
  line-height: 1.45;
}

.eval-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.eval-actions .full-width {
  grid-column: 1 / -1;
}

.error {
  color: #b91c1c;
  margin-top: 8px;
}

.history-list {
  padding-left: 18px;
  font-size: 14px;
  margin: 12px 0 0;
}

.history-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.history-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.mileage-box {
  margin-top: 16px;
  padding: 12px;
  background: #f1f5f9;
  border-radius: 8px;
}

.mileage-box h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.tag {
  font-size: 11px;
  background: #e2e8f0;
  padding: 1px 6px;
  border-radius: 4px;
  margin-right: 4px;
}

.warn {
  color: #991b1b;
}

.meta {
  color: #64748b;
  font-size: 12px;
  display: block;
  margin-top: 4px;
}

.workers-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.workers-head h2 {
  margin: 0;
  font-size: 1.05rem;
}

.count {
  color: #64748b;
  font-weight: 500;
}

.worker-search {
  max-width: 100%;
}

.table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 24px;
}

.desktop-only {
  display: block;
}

.mobile-only {
  display: none;
}

.worker-cards {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.worker-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  background: #fafafa;
}

.worker-card-main {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.worker-no {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e2e8f0;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.worker-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.worker-name {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.worker-card-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 12px;
}

.card-btn {
  min-height: 44px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
}

.card-btn-secondary {
  background: #fff;
  border-color: #cbd5e1;
  color: #334155;
}

.card-btn-primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.card-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.empty-card {
  text-align: center;
  color: #64748b;
  background: #fff;
}

.link-btn {
  background: none;
  border: none;
  color: #2563eb;
  cursor: pointer;
  font-size: 14px;
  padding: 4px 0;
}

@media (max-width: 768px) {
  .desktop-only {
    display: none;
  }

  .mobile-only {
    display: flex;
  }

  .page-head {
    flex-direction: column;
    align-items: stretch;
  }

  .btn-refresh {
    width: 100%;
    min-height: 44px;
  }

  .workers-panel {
    padding: 12px;
  }
}
</style>

<!-- Teleport 모달: scoped 밖 전역 클래스 -->
<style>
.fe-overlay-backdrop {
  position: fixed;
  inset: 0;
  z-index: 400;
  background: rgba(15, 23, 42, 0.45);
}

.fe-modal-panel {
  position: fixed;
  z-index: 410;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: min(480px, calc(100vw - 32px));
  max-height: min(85vh, 640px);
  overflow-y: auto;
  margin: 0;
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.18);
}

.fe-sheet {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 410;
  max-height: min(88vh, 640px);
  overflow-y: auto;
  border-radius: 16px 16px 0 0;
  margin: 0;
  padding: 12px 16px calc(16px + env(safe-area-inset-bottom, 0));
  box-shadow: 0 -8px 32px rgba(15, 23, 42, 0.15);
  transform: translateY(100%);
  transition: transform 0.22s ease;
}

.fe-sheet.fe-sheet-open {
  transform: translateY(0);
}

.fe-sheet-handle {
  width: 40px;
  height: 4px;
  background: #cbd5e1;
  border-radius: 999px;
  margin: 0 auto 12px;
}

.fe-dialog .dialog-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
}

.fe-dialog .dialog-head h2 {
  margin: 0;
  font-size: 1.1rem;
  line-height: 1.35;
  flex: 1;
  min-width: 0;
}

.fe-dialog .dialog-close {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: #f1f5f9;
  color: #475569;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.fe-dialog .dialog-close:hover {
  background: #e2e8f0;
}

.fe-dialog.history-panel .history-list {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

body.fe-sheet-open-body {
  overflow: hidden;
}
</style>
