<template>
  <div class="fe-workspace">
    <!-- 모바일 평가 화면에서 대상자 목록을 표시하는 영역 -->
    <section v-if="isMobileViewport && !evalWorker" class="panel mobile-roster">
      <div class="roster-head">
        <p class="roster-hint">평가를 시작하려면 대상자를 선택해 주세요</p>
      </div>
      <ul class="roster-list">
        <li v-for="(w, idx) in filteredWorkers" :key="w.id">
          <button type="button" class="roster-item" :class="workerRowHighlightClass(w)" @click="selectWorker(w)">
            <span class="roster-no">{{ idx + 1 }}</span>
            <span class="roster-name">{{ formatWorkerLabel(w) }}</span>
            <span v-if="badgeLabel(w)" :class="badgeClass(w)">{{ badgeLabel(w) }}</span>
            <span v-else class="pending-dot" aria-label="미평가" />
          </button>
        </li>
        <li v-if="!filteredWorkers.length" class="empty">조회 결과가 없습니다.</li>
      </ul>
    </section>

    <!-- PC: 데스크톱 목록 + 평가 패널 -->
    <div v-else-if="!isMobileViewport" class="split-layout">
      <aside class="worker-rail panel">
        <ul class="rail-list">
          <li v-for="(w, idx) in filteredWorkers" :key="w.id">
            <button
              type="button"
              class="rail-item"
              :class="[{ active: evalWorker?.id === w.id }, workerRowHighlightClass(w)]"
              @click="selectWorker(w)"
            >
              <span class="rail-no">{{ idx + 1 }}</span>
              <span class="rail-name">{{ formatWorkerLabel(w) }}</span>
              <span v-if="badgeLabel(w)" :class="badgeClass(w)">{{ badgeLabel(w) }}</span>
            </button>
          </li>
        </ul>
      </aside>
      <div class="eval-main">
        <template v-if="evalWorker && props.criteria.length">
          <div v-if="batchPendingWorkers > 0" class="batch-toolbar">
            <button
              class="stitch-btn-secondary batch-toolbar-btn touch-btn-inline"
              type="button"
              :disabled="batchApplyDisabled"
              @click="applyBatchNormal"
            >
              일괄 보통 등록 ({{ batchPendingWorkers }}명)
            </button>
          </div>
          <p v-if="evalError" class="batch-error" role="alert">{{ evalError }}</p>
          <EvalAssessmentSheet
            :worker="evalWorker"
            :title="title"
            :criteria="props.criteria"
            :scores="evalScores"
            :baseline-scores="loadedScores"
            :loading="evalLoading"
            :saving="evalSaving"
            :disabled="periodClosed"
            :error="evalError"
            variant="desktop"
            :preview="evalPreview"
            :eval-kind="evalType === 'SAFETY' ? 'safety' : 'functional'"
            @save="saveEval"
            @update:scores="evalScores = $event"
          />
          <EvalSanctionInline
            v-if="evalType === 'SAFETY'"
            :worker="evalWorker"
            :grouped-violations="groupedViolations"
            :period-closed="periodClosed"
            :prompt-message="sanctionPromptMessage"
            :default-violation-code="inlineDefaultViolationCode"
            :default-note="inlineDefaultNote"
            :prefill-token="sanctionPrefillToken"
            @saved="onSanctionSaved"
            @open-history="emit('open-history', evalWorker.id)"
          />
          <EvalRewardInline
            v-if="evalType === 'SAFETY'"
            :worker="evalWorker"
            :period-closed="periodClosed"
            :evaluation-locked="evaluationLocked"
            @saved="onRewardSaved"
          />
        </template>
        <div v-else class="eval-placeholder panel">
          <p>왼쪽에서 근로자를 선택하세요.</p>
        </div>
      </div>
    </div>

    <!-- 모바일: 평가 바텀시트 (Teleport — fe-sheet 스타일은 styles.css 전역) -->
    <Teleport to="body">
      <template v-if="isMobileViewport && evalWorker && props.criteria.length">
        <div class="fe-sheet-backdrop" aria-hidden="true" @click="closeEval" />
        <div class="fe-sheet fe-sheet-open" role="dialog" aria-modal="true" :aria-label="`${evalWorker.name} ${title}`">
          <div class="fe-sheet-handle" aria-hidden="true" />
          <div v-if="batchPendingWorkers > 0" class="batch-toolbar">
            <button
              class="stitch-btn-secondary batch-toolbar-btn touch-btn-inline"
              type="button"
              :disabled="batchApplyDisabled"
              @click="applyBatchNormal"
            >
              일괄 보통 등록 ({{ batchPendingWorkers }}명)
            </button>
          </div>
          <p v-if="evalError" class="batch-error" role="alert">{{ evalError }}</p>
          <EvalAssessmentSheet
            :worker="evalWorker"
            :title="title"
            :criteria="props.criteria"
            :scores="evalScores"
            :baseline-scores="loadedScores"
            :loading="evalLoading"
            :saving="evalSaving"
            :disabled="periodClosed"
            :error="evalError"
            variant="mobile"
            :preview="evalPreview"
            :eval-kind="evalType === 'SAFETY' ? 'safety' : 'functional'"
            @save="saveEval"
            @close="closeEval"
            @update:scores="evalScores = $event"
          />
          <EvalSanctionInline
            v-if="evalType === 'SAFETY'"
            :worker="evalWorker"
            :grouped-violations="groupedViolations"
            :period-closed="periodClosed"
            :prompt-message="sanctionPromptMessage"
            :default-violation-code="inlineDefaultViolationCode"
            :default-note="inlineDefaultNote"
            :prefill-token="sanctionPrefillToken"
            @saved="onSanctionSaved"
            @open-history="emit('open-history', evalWorker.id)"
          />
          <EvalRewardInline
            v-if="evalType === 'SAFETY'"
            :worker="evalWorker"
            :period-closed="periodClosed"
            :evaluation-locked="evaluationLocked"
            @saved="onRewardSaved"
          />
        </div>
      </template>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import EvalAssessmentSheet from "@/components/functional-eval/EvalAssessmentSheet.vue";
import EvalSanctionInline from "@/components/functional-eval/EvalSanctionInline.vue";
import EvalRewardInline from "@/components/functional-eval/EvalRewardInline.vue";
import type { Criterion } from "@/components/functional-eval/EvalAssessmentSheet.vue";
import { useMobileViewport } from "@/composables/useMobileViewport";
import { api } from "@/services/api";
import {
  completionBadge,
  completionBadgeClass,
  isFunctionalComplete,
  isSafetyComplete,
  isFullyComplete,
  scoreRatioToGradeLabel,
  workerRowHighlightClass,
} from "@/utils/functionalEvalCompletion";
import { buildSanctionPrefillFromSafetyScores } from "@/utils/safetySanctionMapping";
import { isFeGuidePreview } from "@/utils/feGuidePreview";

export type EvalType = "FUNCTIONAL" | "SAFETY";

export interface AssessmentBrief {
  scores: Record<string, string>;
  total_score: number;
  max_score: number;
  grade_code: string;
  grade_label: string;
  is_complete: boolean;
}

export interface EvalWorker {
  id: number;
  row_no: number;
  name: string;
  eval_assignment?: "DIRECT" | "TEAM" | "TEAM_LEADER";
  sanction_status?: string;
  sanction_status_label?: string;
  is_permanently_expelled?: boolean;
  functional_assessment?: AssessmentBrief | null;
  safety_assessment?: AssessmentBrief | null;
  customer_reward?: { id: number; status: string; bonus_points?: number } | null;
}

interface ViolationGroup {
  category: string;
  label: string;
  items: { code: string; category: string; category_label: string; label: string }[];
}

const props = defineProps<{
  workers: EvalWorker[];
  evalType: EvalType;
  title: string;
  criteria: Criterion[];
  periodClosed: boolean;
  evaluationLocked?: boolean;
  reload: () => Promise<void>;
  focusWorkerId: number | null;
  autoPickOnMount?: boolean;
  groupedViolations?: ViolationGroup[];
  sanctionPromptMessage?: string;
  defaultViolationCode?: string;
}>();

const emit = defineEmits<{
  "request-safety": [workerId: number];
  "safety-saved": [worker: EvalWorker];
  "revision-saved": [worker: EvalWorker];
  "sanction-saved": [];
  "reward-saved": [];
  "open-history": [workerId: number];
}>();

const groupedViolations = computed(() => props.groupedViolations || []);

const { isMobileViewport } = useMobileViewport();

const evalWorker = ref<EvalWorker | null>(null);
const evalScores = ref<Record<string, string>>({});
const loadedScores = ref<Record<string, string>>({});
const evalLoading = ref(false);
const evalSaving = ref(false);
const evalError = ref("");
const sanctionPrefillToken = ref(0);
const inlineSanctionPrefill = ref<{ violationCode: string; note: string } | null>(null);

const inlineDefaultViolationCode = computed(
  () => inlineSanctionPrefill.value?.violationCode || props.defaultViolationCode || "",
);
const inlineDefaultNote = computed(() => inlineSanctionPrefill.value?.note || "");

const batchPendingWorkers = computed(() =>
  filteredWorkers.value.filter((w) => (props.evalType === "FUNCTIONAL" ? !isFunctionalComplete(w) : !isSafetyComplete(w))).length,
);
const batchApplyDisabled = computed(
  () => props.periodClosed || evalSaving.value || evalLoading.value || props.criteria.length === 0 || batchPendingWorkers.value === 0,
);

const shortTitle = computed(() => (props.evalType === "SAFETY" ? "2-2 안전·제재" : "2-1 기능"));

const filteredWorkers = computed(() =>
  [...props.workers].sort((a, b) => a.name.localeCompare(b.name, "ko")),
);

function badgeLabel(w: EvalWorker) {
  return completionBadge(w);
}

function badgeClass(w: EvalWorker) {
  return completionBadgeClass(completionBadge(w));
}

function assignmentLabel(assignment?: EvalWorker["eval_assignment"]) {
  if (assignment === "DIRECT") return "직영";
  if (assignment === "TEAM") return "팀원";
  if (assignment === "TEAM_LEADER") return "팀장";
  return "";
}

function formatWorkerLabel(w: EvalWorker) {
  const assignment = assignmentLabel(w.eval_assignment);
  return assignment ? `${w.name} ${assignment}` : w.name;
}

const evalPreview = computed(() => {
  const list = props.criteria;
  if (!list.length) return null;
  let total = 0;
  let max = 0;
  for (const c of list) {
    const key = evalScores.value[c.id];
    const g = c.grades.find((x) => x.key === key);
    if (!g) return null;
    total += g.points;
    max += Math.max(...c.grades.map((x) => x.points));
  }
  const ratio = max ? total / max : 0;
  return { total_score: total, max_score: max, grade_label: scoreRatioToGradeLabel(ratio) };
});

function applyInlineSanctionPrefill(scores: Record<string, string>) {
  if (props.evalType !== "SAFETY") {
    inlineSanctionPrefill.value = null;
    return;
  }
  const prefill = buildSanctionPrefillFromSafetyScores(scores, props.criteria);
  if (prefill) {
    inlineSanctionPrefill.value = prefill;
    sanctionPrefillToken.value += 1;
  } else {
    inlineSanctionPrefill.value = null;
  }
}

async function loadScores(worker: EvalWorker) {
  evalLoading.value = true;
  evalError.value = "";
  try {
    const res = await api.get(`/functional-eval/workers/${worker.id}/assessment/${props.evalType}`);
    const existing = res.data.assessment?.scores as Record<string, string> | undefined;
    const scores: Record<string, string> = {};
    for (const c of props.criteria) {
      scores[c.id] = existing?.[c.id] || "";
    }
    evalScores.value = scores;
    loadedScores.value = { ...scores };
    applyInlineSanctionPrefill(scores);
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    evalError.value = typeof detail === "string" && detail ? formatLoadError(detail, status) : formatLoadError("LOAD_ERROR", status);
  } finally {
    evalLoading.value = false;
  }
}

function formatLoadError(detail: string, status?: number) {
  if (detail === "CANNOT_EVALUATE_SELF") return "자기 자신은 평가할 수 없습니다.";
  if (detail === "CANNOT_EVALUATE_SITE_MANAGER") return "소장은 평가할 수 없습니다.";
  if (detail === "SITE_MISMATCH") return "현재 사용자에게 평가 권한이 없는 대상자입니다.";
  if (detail === "WORKER_NOT_FOUND") return "대상자 정보를 찾을 수 없습니다.";
  if (detail === "WORKER_NOT_ON_ATTENDANCE" || detail.includes("근태")) return "근태 정보가 없어서 평가를 시작할 수 없습니다.";
  if (detail === "NO_ATTENDANCE_UPLOAD") return "근태 업로드가 필요합니다. 근태 업로드 후 다시 시도하세요.";
  if (status === 403) return "권한이 없어 평가 항목을 불러올 수 없습니다.";
  if (status === 404) return "대상자를 찾을 수 없습니다.";
  if (status === 409) return "평가 항목 조회가 일시적으로 제한되었습니다.";
  if (detail && detail !== "LOAD_ERROR") return detail;
  return "평가 항목을 불러오는 중 오류가 발생했습니다.";
}

async function selectWorker(worker: EvalWorker) {
  evalWorker.value = worker;
  if (isMobileViewport.value) {
    document.body.classList.add("fe-sheet-open-body");
  }
  await loadScores(worker);
}

function closeEval() {
  evalWorker.value = null;
  evalScores.value = {};
  loadedScores.value = {};
  evalError.value = "";
  inlineSanctionPrefill.value = null;
  document.body.classList.remove("fe-sheet-open-body");
}

async function onSanctionSaved() {
  await props.reload();
  const updated = props.workers.find((w) => w.id === evalWorker.value?.id);
  if (updated) {
    evalWorker.value = updated;
    if (props.evalType === "SAFETY") {
      await loadScores(updated);
    }
  }
  emit("sanction-saved");
}

async function onRewardSaved() {
  await props.reload();
  const updated = props.workers.find((w) => w.id === evalWorker.value?.id);
  if (updated) {
    evalWorker.value = updated;
  }
  emit("reward-saved");
}

async function saveEval(scoresOverride?: Record<string, string>) {
  if (!evalWorker.value || evalSaving.value) return;
  const scores = scoresOverride ?? evalScores.value;
  if (scoresOverride) {
    evalScores.value = scoresOverride;
  }
  const savedId = evalWorker.value.id;
  const wasFunctionalDone = isFunctionalComplete(evalWorker.value);
  const wasSafetyDone = isSafetyComplete(evalWorker.value);
  const isRevision =
    props.evalType === "FUNCTIONAL" ? wasFunctionalDone : wasSafetyDone;
  evalSaving.value = true;
  evalError.value = "";
  try {
    await api.put(`/functional-eval/workers/${evalWorker.value.id}/assessment/${props.evalType}`, {
      scores,
    });
    await props.reload();
    const updated = props.workers.find((w) => w.id === savedId);
    if (updated) evalWorker.value = updated;
    loadedScores.value = { ...scores };
    applyInlineSanctionPrefill(scores);

    if (isRevision) {
      if (updated) {
        if (props.evalType === "SAFETY") {
          emit("safety-saved", updated);
        } else {
          emit("revision-saved", updated);
        }
      }
      return;
    }

    if (props.evalType === "FUNCTIONAL" && updated) {
      if (!isSafetyComplete(updated)) {
        emit("request-safety", savedId);
        return;
      }
      if (isFullyComplete(updated)) {
        emit("safety-saved", updated);
      }
      return;
    }

    if (props.evalType === "SAFETY" && updated) {
      emit("safety-saved", updated);
      if (isMobileViewport.value) {
        closeEval();
      }
    }
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    if (msg === "EVALUATION_SIGNATURE_LOCKED") {
      evalError.value = "서명 완료 후에는 평가를 수정할 수 없습니다.";
    } else {
      evalError.value = typeof msg === "string" ? msg : "요청을 처리하는 중에 오류가 발생했습니다.";
    }
  } finally {
    evalSaving.value = false;
  }
}

function normalGradeKey(c: Criterion): string | null {
  const byLabel = c.grades.find((g) => g.label.includes("보통"));
  if (byLabel) return byLabel.key;
  if (!c.grades.length) return null;
  const index = Math.floor((c.grades.length - 1) / 2);
  return c.grades[index]?.key ?? null;
}

function buildNormalScores(): Record<string, string> {
  const scores: Record<string, string> = {};
  for (const c of props.criteria) {
    const gradeKey = normalGradeKey(c);
    if (gradeKey) scores[String(c.id)] = gradeKey;
  }
  return scores;
}

function formatSaveError(e: unknown): string {
  const status = (e as { response?: { status?: number } })?.response?.status;
  const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  if (msg === "EVALUATION_SIGNATURE_LOCKED") return "서명 완료 후 수정 불가";
  if (msg === "CANNOT_EVALUATE_SELF") return "본인 평가 불가";
  if (msg === "SITE_MISMATCH") return "평가 권한 없음";
  if (typeof msg === "string" && msg.startsWith("INCOMPLETE:")) return "항목 누락";
  if (typeof msg === "string" && msg) return msg;
  if (status === 401) return "로그인 만료";
  return "저장 실패";
}

async function applyBatchNormal() {
  if (batchApplyDisabled.value || !props.criteria.length) return;
  const scorePayload = buildNormalScores();
  const requiredIds = props.criteria.map((c) => String(c.id));
  if (requiredIds.some((id) => !scorePayload[id])) {
    evalError.value = "보통 등급 기준을 구성할 수 없습니다. 항목 정의를 확인하세요.";
    return;
  }

  const targets = filteredWorkers.value.filter((w) =>
    props.evalType === "FUNCTIONAL" ? !isFunctionalComplete(w) : !isSafetyComplete(w),
  );
  if (!targets.length) return;

  evalSaving.value = true;
  evalError.value = "";
  const failures: string[] = [];
  let saved = 0;
  try {
    for (const target of targets) {
      try {
        await api.put(`/functional-eval/workers/${target.id}/assessment/${props.evalType}`, {
          scores: scorePayload,
        });
        saved += 1;
      } catch (e: unknown) {
        failures.push(`${target.name}: ${formatSaveError(e)}`);
      }
    }
    await props.reload();
    if (evalWorker.value) {
      const refreshed = props.workers.find((w) => w.id === evalWorker.value?.id);
      evalWorker.value = refreshed ?? evalWorker.value;
      if (refreshed) await loadScores(refreshed);
    }
    if (failures.length) {
      const head = failures.slice(0, 2).join(" · ");
      const tail = failures.length > 2 ? ` 외 ${failures.length - 2}명` : "";
      evalError.value = saved
        ? `${saved}명 저장, 실패 ${failures.length}명 — ${head}${tail}`
        : `일괄 저장 실패 — ${head}${tail}`;
    } else if (props.evalType === "FUNCTIONAL" && evalWorker.value && !isSafetyComplete(evalWorker.value)) {
      emit("request-safety", evalWorker.value.id);
      return;
    } else if (props.evalType === "SAFETY" && evalWorker.value) {
      emit("safety-saved", evalWorker.value);
    }
  } catch {
    evalError.value = "일괄 저장 중 오류가 발생했습니다.";
  } finally {
    evalSaving.value = false;
  }
}

async function pickInitialWorker() {
  if (props.focusWorkerId) {
    const focused = props.workers.find((w) => w.id === props.focusWorkerId);
    if (focused) {
      await selectWorker(focused);
      return;
    }
  }
  if (props.autoPickOnMount === false) return;
  if (filteredWorkers.value.length) {
    if (isFeGuidePreview()) {
      await selectWorker(filteredWorkers.value[0]);
      return;
    }
    if (!isMobileViewport.value) {
      const firstIncomplete = filteredWorkers.value.find((w) => !isFullyComplete(w));
      await selectWorker(firstIncomplete ?? filteredWorkers.value[0]);
    }
  }
}

onMounted(() => {
  void pickInitialWorker();
});

onBeforeUnmount(() => {
  document.body.classList.remove("fe-sheet-open-body");
});

watch(
  () => props.focusWorkerId,
  (id) => {
    if (id == null) return;
    const focused = props.workers.find((w) => w.id === id);
    if (focused && evalWorker.value?.id !== id) {
      void selectWorker(focused);
    }
  },
);

watch(
  () => props.evalType,
  () => {
    if (evalWorker.value) {
      void loadScores(evalWorker.value);
    }
  },
);
</script>

<style scoped>
.fe-workspace {
  min-height: auto;
}

.split-layout {
  display: grid;
  grid-template-columns: minmax(200px, 260px) minmax(0, 1fr);
  gap: 12px;
  min-height: 0;
  max-height: min(72vh, calc(100vh - 220px));
  align-items: stretch;
}

.worker-rail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  max-height: 100%;
  padding: 12px;
  overflow: hidden;
}

.rail-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.rail-item.row-highlight--alert {
  background: #fef2f2;
}

.rail-item.row-highlight--alert:hover {
  background: #fee2e2;
}

.rail-item.row-highlight--alert.active {
  background: #fecaca;
  box-shadow: inset 3px 0 0 #dc2626;
}

.roster-item.row-highlight--alert {
  background: #fef2f2;
}

.roster-item.row-highlight--alert:hover {
  background: #fee2e2;
}

.rail-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 8px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-size: 14px;
}

.rail-item:hover {
  background: #f1f5f9;
}

.rail-item.active {
  background: #eff6ff;
  box-shadow: inset 3px 0 0 #2563eb;
}

.rail-no {
  flex-shrink: 0;
  width: 22px;
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}

.rail-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
  color: #0f172a;
}

.done-badge {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
}

.done-badge--full {
  background: #dcfce7;
  color: #166534;
}

.done-badge--functional {
  background: #dbeafe;
  color: #1d4ed8;
}

.done-badge--safety {
  background: #e0e7ff;
  color: #4338ca;
}

.eval-main {
  min-width: 0;
  min-height: 0;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.eval-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  min-height: 200px;
}

.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.mobile-roster {
  padding: 12px;
  padding-bottom: 4px;
}

.roster-list > li:last-child .roster-item {
  margin-bottom: 4px;
}

.roster-head {
  margin-bottom: 10px;
}

.roster-hint {
  margin: 8px 0 0;
  font-size: 13px;
  color: #64748b;
}

.field-control {
  width: 100%;
  box-sizing: border-box;
  font-size: 16px;
}

.roster-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.roster-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 4px;
  border: none;
  border-bottom: 1px solid #f1f5f9;
  background: #fff;
  cursor: pointer;
  text-align: left;
}

.roster-no {
  width: 24px;
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}

.roster-name {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
}

.pending-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f59e0b;
  flex-shrink: 0;
}

.empty {
  padding: 24px;
  text-align: center;
  color: #64748b;
}

.batch-toolbar {
  margin-bottom: 8px;
  display: flex;
  justify-content: flex-start;
}

.batch-toolbar-btn {
  width: fit-content;
  min-height: 40px;
}

.batch-error {
  margin: 0 0 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  font-size: 13px;
  line-height: 1.45;
  max-width: 100%;
}

@media (max-width: 768px) {
  .fe-workspace {
    min-height: auto;
  }
}
</style>

