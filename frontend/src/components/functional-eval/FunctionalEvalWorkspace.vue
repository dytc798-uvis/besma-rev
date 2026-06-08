<template>
  <div class="fe-workspace">
    <!-- 모바일: 명단 화면 (평가 중이 아닐 때) -->
    <section v-if="isMobileViewport && !evalWorker" class="panel mobile-roster">
      <div class="roster-head">
        <input
          v-model.trim="workerSearch"
          type="search"
          class="field-control"
          placeholder="이름 검색"
          autocomplete="off"
        />
        <p class="roster-hint">근로자를 선택하면 {{ shortTitle }} 평가를 입력합니다.</p>
      </div>
      <ul class="roster-list">
        <li v-for="(w, idx) in filteredWorkers" :key="w.id">
          <button type="button" class="roster-item" :class="workerRowHighlightClass(w)" @click="selectWorker(w)">
            <span class="roster-no">{{ idx + 1 }}</span>
            <span class="roster-name">{{ w.name }}</span>
            <span v-if="badgeLabel(w)" :class="badgeClass(w)">{{ badgeLabel(w) }}</span>
            <span v-else class="pending-dot" aria-label="미평가" />
          </button>
        </li>
        <li v-if="!filteredWorkers.length" class="empty">검색 결과가 없습니다.</li>
      </ul>
    </section>

    <!-- PC: 좌측 명단 + 우측 평가 -->
    <div v-else-if="!isMobileViewport" class="split-layout">
      <aside class="worker-rail panel">
        <input
          v-model.trim="workerSearch"
          type="search"
          class="field-control rail-search"
          placeholder="이름 검색"
        />
        <ul class="rail-list">
          <li v-for="(w, idx) in filteredWorkers" :key="w.id">
            <button
              type="button"
              class="rail-item"
              :class="[{ active: evalWorker?.id === w.id }, workerRowHighlightClass(w)]"
              @click="selectWorker(w)"
            >
              <span class="rail-no">{{ idx + 1 }}</span>
              <span class="rail-name">{{ w.name }}</span>
              <span v-if="badgeLabel(w)" :class="badgeClass(w)">{{ badgeLabel(w) }}</span>
            </button>
          </li>
        </ul>
      </aside>
      <div class="eval-main">
        <template v-if="evalWorker && criteria.length">
          <EvalAssessmentSheet
            :worker="evalWorker"
            :title="title"
            :criteria="criteria"
            :scores="evalScores"
            :loading="evalLoading"
            :saving="evalSaving"
            :disabled="periodClosed"
            :error="evalError"
            variant="desktop"
            :preview="evalPreview"
            :save-label="desktopSaveLabel"
            @save="saveEval(isMobileViewport)"
            @update:scores="evalScores = $event"
          />
          <EvalSanctionInline
            v-if="evalType === 'SAFETY'"
            :worker="evalWorker"
            :grouped-violations="groupedViolations"
            :period-closed="periodClosed"
            :prompt-message="sanctionPromptMessage"
            :default-violation-code="defaultViolationCode"
            @saved="onSanctionSaved"
            @open-history="emit('open-history', evalWorker.id)"
          />
        </template>
        <div v-else class="eval-placeholder panel">
          <p>왼쪽에서 근로자를 선택하세요.</p>
        </div>
      </div>
    </div>

    <!-- 모바일: 평가 모달 -->
    <Teleport to="body">
      <div
        v-if="isMobileViewport && evalWorker"
        class="fe-sheet-backdrop"
        aria-hidden="true"
        @click="closeEval"
      />
      <EvalAssessmentSheet
        v-if="isMobileViewport && evalWorker && criteria.length"
        :worker="evalWorker"
        :title="title"
        :criteria="criteria"
        :scores="evalScores"
        :loading="evalLoading"
        :saving="evalSaving"
        :disabled="periodClosed"
        :error="evalError"
        variant="mobile"
        :preview="evalPreview"
        :save-label="mobileSaveLabel"
        @close="closeEval"
        @save="saveEval(true)"
        @update:scores="evalScores = $event"
      />
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import EvalAssessmentSheet from "@/components/functional-eval/EvalAssessmentSheet.vue";
import EvalSanctionInline from "@/components/functional-eval/EvalSanctionInline.vue";
import type { Criterion } from "@/components/functional-eval/EvalAssessmentSheet.vue";
import { useMobileViewport } from "@/composables/useMobileViewport";
import { api } from "@/services/api";
import {
  completionBadge,
  completionBadgeClass,
  isSafetyComplete,
  isFullyComplete,
  scoreRatioToGradeLabel,
  workerRowHighlightClass,
} from "@/utils/functionalEvalCompletion";

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
  sanction_status?: string;
  sanction_status_label?: string;
  is_permanently_expelled?: boolean;
  functional_assessment?: AssessmentBrief | null;
  safety_assessment?: AssessmentBrief | null;
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
  "sanction-saved": [];
  "open-history": [workerId: number];
}>();

const groupedViolations = computed(() => props.groupedViolations || []);

const { isMobileViewport } = useMobileViewport();

const workerSearch = ref("");
const evalWorker = ref<EvalWorker | null>(null);
const evalScores = ref<Record<string, string>>({});
const evalLoading = ref(false);
const evalSaving = ref(false);
const evalError = ref("");

const shortTitle = computed(() => (props.evalType === "SAFETY" ? "2-2 안전·제재" : "2-1 기능"));

const filteredWorkers = computed(() => {
  const q = workerSearch.value.toLowerCase();
  if (!q) return props.workers;
  return props.workers.filter((w) => w.name.toLowerCase().includes(q));
});

function badgeLabel(w: EvalWorker) {
  return completionBadge(w);
}

function badgeClass(w: EvalWorker) {
  return completionBadgeClass(completionBadge(w));
}

const mobileSaveLabel = computed(() => {
  const w = evalWorker.value;
  if (props.evalType === "FUNCTIONAL" && w && !isSafetyComplete(w)) {
    return "저장 후 안전평가";
  }
  return nextIncompleteWorker(evalWorker.value?.id ?? null) ? "저장 후 다음" : "평가 저장";
});

const desktopSaveLabel = computed(() => {
  const w = evalWorker.value;
  if (props.evalType === "FUNCTIONAL" && w && !isSafetyComplete(w)) {
    return "저장 후 안전평가";
  }
  return "평가 저장";
});

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

function nextIncompleteWorker(afterId: number | null): EvalWorker | null {
  const list = filteredWorkers.value;
  if (!list.length) return null;
  const start = afterId == null ? 0 : list.findIndex((w) => w.id === afterId) + 1;
  for (let i = start; i < list.length; i++) {
    if (!isFullyComplete(list[i])) return list[i];
  }
  for (let i = 0; afterId != null && i < start; i++) {
    if (!isFullyComplete(list[i])) return list[i];
  }
  return null;
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
  } catch {
    evalError.value = "평가표를 불러오지 못했습니다.";
  } finally {
    evalLoading.value = false;
  }
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
  evalError.value = "";
  document.body.classList.remove("fe-sheet-open-body");
}

async function onSanctionSaved() {
  await props.reload();
  const updated = props.workers.find((w) => w.id === evalWorker.value?.id);
  if (updated) evalWorker.value = updated;
  emit("sanction-saved");
}

async function saveEval(advanceOnMobile: boolean) {
  if (!evalWorker.value) return;
  const savedId = evalWorker.value.id;
  evalSaving.value = true;
  evalError.value = "";
  try {
    await api.put(`/functional-eval/workers/${evalWorker.value.id}/assessment/${props.evalType}`, {
      scores: evalScores.value,
    });
    await props.reload();
    const updated = props.workers.find((w) => w.id === savedId);
    if (updated) evalWorker.value = updated;

    if (props.evalType === "FUNCTIONAL" && updated && !isSafetyComplete(updated)) {
      emit("request-safety", savedId);
      return;
    }

    if (props.evalType === "SAFETY" && updated) {
      emit("safety-saved", updated);
    }

    if (advanceOnMobile && isMobileViewport.value) {
      const next = nextIncompleteWorker(savedId);
      if (next) {
        await selectWorker(next);
      } else {
        closeEval();
      }
    }
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    evalError.value = typeof msg === "string" ? msg : "평가 저장에 실패했습니다.";
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
  if (!isMobileViewport.value && filteredWorkers.value.length) {
    const firstIncomplete = filteredWorkers.value.find((w) => !isFullyComplete(w));
    await selectWorker(firstIncomplete ?? filteredWorkers.value[0]);
  }
}

onMounted(() => {
  void pickInitialWorker();
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
</script>

<style scoped>
.fe-workspace {
  min-height: auto;
}

.split-layout {
  display: grid;
  grid-template-columns: minmax(200px, 260px) minmax(0, 1fr);
  gap: 12px;
  min-height: auto;
  align-items: start;
}

.worker-rail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 12px;
  overflow: hidden;
}

.rail-search {
  flex-shrink: 0;
  margin-bottom: 10px;
  font-size: 14px;
  padding: 8px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  width: 100%;
  box-sizing: border-box;
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
  display: flex;
  flex-direction: column;
  align-items: flex-start;
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

@media (max-width: 768px) {
  .fe-workspace {
    min-height: auto;
  }
}
</style>
