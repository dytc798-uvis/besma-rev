<template>
  <section
    class="decision-panel"
    :class="{ 'decision-panel--compact': compactLayout }"
    :aria-label="ariaLabel"
  >
    <header class="decision-panel-head">
      <h2 class="decision-panel-title">{{ panelTitle }}</h2>
      <span v-if="decisions.length > 0" class="decision-panel-count">{{ decisions.length }}건</span>
      <span v-else-if="enrichedLogs.length > 0" class="decision-panel-badge-muted">미결정 없음</span>
      <span v-else class="decision-panel-badge-muted">미결정 없음 · 메모 가능</span>
    </header>

    <p v-if="decisions.length > 0" class="decision-panel-hint">
      <strong>검토안 복사</strong>는 공유·검토용입니다. 처리 시 클립보드에는
      <strong>「Cursor 실행 지시」</strong> 블록(구현 지시 + 조건)이 복사됩니다.
      <strong>승인</strong>만 <code>execution_ready</code> 로 Export JSON에 표시됩니다.
    </p>
    <p v-else-if="enrichedLogs.length > 0" class="decision-panel-hint decision-panel-hint--compact">
      미결정 항목은 없습니다. 아래에서 이 화면에 대한 말을 남기거나, 로그를 Export 하세요.
    </p>
    <p v-else class="decision-panel-hint decision-panel-hint--compact">
      미결정 항목이 없어도, 이 화면에서 하고 싶은 개선·요청을 아래에 적고 저장하거나 Cursor용으로 복사할 수 있습니다.
    </p>

    <p v-if="copyHint" class="copy-hint" :class="{ 'copy-hint--error': copyHintIsError }" role="status">
      {{ copyHint }}
    </p>

    <div class="scope-page-note-section">
      <p class="scope-page-note-title">이 화면에서 하고 싶은 것</p>
      <p class="scope-page-note-desc">
        scope: <code class="scope-code">{{ scope }}</code>
      </p>
      <textarea
        v-model="pageIntentDraft"
        class="scope-page-note-textarea"
        rows="3"
        placeholder="예: 이 목록에 열 정렬을 넣고, 기본은 미제출 우선으로 해줘"
        aria-label="이 화면 scope 메모"
      />
      <div class="scope-page-note-actions">
        <button type="button" class="btn-scope-save" @click="onSavePageIntent">저장</button>
        <button type="button" class="btn-scope-copy" @click="onCopyPageIntent">Cursor용 복사</button>
        <span v-if="pageIntentFeedback" class="scope-page-note-feedback">{{ pageIntentFeedback }}</span>
        <span v-else-if="savedPageIntentAt" class="scope-page-note-saved-at">마지막 저장: {{ savedPageIntentAt }}</span>
      </div>
    </div>

    <ul v-if="decisions.length > 0" class="decision-panel-list">
      <DecisionItem
        v-for="d in decisions"
        :key="d.id"
        :decision-id="d.id"
        :scope="scope"
        :title="d.title"
        :summary="d.summary"
        :ref-doc="d.refDoc"
        :options="d.options"
        @action="
          onAction(d, $event.action, $event.selectedOption, $event.note, $event.implementationDirective)
        "
      />
    </ul>

    <div v-if="enrichedLogs.length > 0" class="export-section">
      <p class="export-title">결정 내역 Export (세션 전체 {{ enrichedLogs.length }}건)</p>
      <p class="export-desc">
        각 항목에 <code>implementation_instruction</code>(= note),
        <code>execution_ready</code>(승인만 true), <code>cursor_execution_markdown</code>이 포함됩니다.
      </p>
      <div class="export-actions">
        <button type="button" class="btn-export" @click="doExportMarkdown">Export Markdown</button>
        <button type="button" class="btn-export" @click="doExportJson">Export JSON</button>
        <button type="button" class="btn-export btn-export-secondary" @click="copyAllMarkdown">
          전체 Markdown 복사
        </button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useDecisionState } from "@/composables/useDecisionState";
import type { DecisionAction, DecisionRecord } from "@/services/decisionService";
import {
  attachTitlesToLogs,
  copyTextToClipboard,
  downloadTextFile,
  exportAllLogsJson,
  exportAllLogsMarkdown,
  formatScopePageIntentMarkdown,
} from "@/services/decisionCursorExport";
import DecisionItem from "./DecisionItem.vue";

const props = defineProps<{
  scope: string;
}>();

const {
  openDecisionsForScope,
  resolveDecision,
  decisionLogs,
  decisionItems,
  scopePageNotesByScope,
  saveScopePageNote,
} = useDecisionState();
const decisions = computed(() => openDecisionsForScope(props.scope));
const enrichedLogs = computed(() => attachTitlesToLogs(decisionLogs.value, decisionItems.value));

/** OPEN 미결정이 없으면 여백을 줄인 레이아웃 */
const compactLayout = computed(() => decisions.value.length === 0);

const panelTitle = computed(() => {
  if (decisions.value.length > 0) return "미결정 사항";
  if (enrichedLogs.value.length > 0) return "결정 처리 내역 · Export";
  return "이 화면 표현";
});
const ariaLabel = computed(() => `Decision 패널 ${props.scope}`);

const copyHint = ref("");
const copyHintIsError = ref(false);

const pageIntentDraft = ref("");
const pageIntentFeedback = ref("");
const savedPageIntentAt = computed(() => {
  const at = scopePageNotesByScope.value[props.scope]?.updated_at;
  if (!at) return "";
  try {
    return new Date(at).toLocaleString("ko-KR", {
      dateStyle: "short",
      timeStyle: "short",
      timeZone: "Asia/Seoul",
    });
  } catch {
    return at;
  }
});

watch(
  () => props.scope,
  (s) => {
    pageIntentDraft.value = scopePageNotesByScope.value[s]?.text ?? "";
  },
  { immediate: true },
);

function onSavePageIntent() {
  saveScopePageNote(props.scope, pageIntentDraft.value);
  pageIntentFeedback.value = "저장됨 (브라우저에 유지)";
  window.setTimeout(() => {
    pageIntentFeedback.value = "";
  }, 2500);
}

async function onCopyPageIntent() {
  const entry = scopePageNotesByScope.value[props.scope];
  const savedText = entry?.text?.trim() ?? "";
  const draftText = pageIntentDraft.value.trim();
  const text = draftText || savedText;
  if (!text) {
    copyHintIsError.value = true;
    copyHint.value = "복사할 내용이 없습니다. 메모를 입력하거나 먼저 저장하세요.";
    window.setTimeout(() => {
      copyHint.value = "";
      copyHintIsError.value = false;
    }, 4000);
    return;
  }
  const updated_at =
    savedText && text === savedText && entry?.updated_at ? entry.updated_at : undefined;
  const md = formatScopePageIntentMarkdown({
    scope: props.scope,
    text,
    updated_at,
  });
  const ok = await copyTextToClipboard(md);
  copyHintIsError.value = false;
  copyHint.value = ok
    ? "페이지 표현(메모)이 클립보드에 복사되었습니다."
    : "클립보드 복사에 실패했습니다.";
  window.setTimeout(() => {
    copyHint.value = "";
  }, 5000);
}

async function onAction(
  row: DecisionRecord,
  action: DecisionAction,
  selectedOption: string,
  note: string,
  implementationDirective: string,
) {
  const res = resolveDecision(row.id, action, selectedOption, note, implementationDirective ?? "");
  if (!res.ok) {
    copyHintIsError.value = true;
    if (res.reason === "EMPTY_APPROVAL_INSTRUCTION") {
      copyHint.value = "승인하려면 구현 지시를 입력해야 합니다.";
    } else if (res.reason === "VAGUE_APPROVAL_INSTRUCTION") {
      copyHint.value =
        "구현 지시가 모호합니다. ‘추후 구현 예정’ 등이 아니라, 무엇을 어떻게 바꿀지 구체적으로 적어주세요.";
    }
    window.setTimeout(() => {
      copyHint.value = "";
      copyHintIsError.value = false;
    }, 5000);
    return;
  }

  copyHintIsError.value = false;
  const ok = await copyTextToClipboard(res.cursor_execution_markdown);
  copyHint.value = ok
    ? "Cursor 실행 지시가 클립보드에 복사되었습니다. Cursor에 붙여넣으세요."
    : "클립보드 복사에 실패했습니다. 브라우저 권한을 확인하세요.";
  window.setTimeout(() => {
    copyHint.value = "";
  }, 5000);
}

function stampFilename(ext: string) {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `besma-decisions-${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}.${ext}`;
}

function doExportMarkdown() {
  downloadTextFile(stampFilename("md"), exportAllLogsMarkdown(enrichedLogs.value), "text/markdown");
}

function doExportJson() {
  downloadTextFile(stampFilename("json"), exportAllLogsJson(enrichedLogs.value), "application/json");
}

async function copyAllMarkdown() {
  copyHintIsError.value = false;
  const md = exportAllLogsMarkdown(enrichedLogs.value);
  const ok = await copyTextToClipboard(md);
  copyHint.value = ok ? "전체 Markdown(Cursor 실행 지시)이 클립보드에 복사되었습니다." : "복사에 실패했습니다.";
  window.setTimeout(() => {
    copyHint.value = "";
  }, 5000);
}
</script>

<style scoped>
.decision-panel {
  margin-bottom: 20px;
  padding: 16px 18px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.decision-panel--compact {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  box-shadow: none;
}

.decision-panel--compact .decision-panel-head {
  margin-bottom: 4px;
}

.decision-panel--compact .decision-panel-title {
  font-size: 13px;
}

.decision-panel-hint--compact {
  margin-bottom: 6px;
  font-size: 11px;
}

.decision-panel--compact .export-section {
  margin-top: 10px;
  padding-top: 10px;
}

.decision-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.decision-panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  flex: 1;
  min-width: 0;
}

.decision-panel-count {
  font-size: 12px;
  font-weight: 700;
  color: #b45309;
  background: #fffbeb;
  border: 1px solid #fde68a;
  padding: 4px 10px;
  border-radius: 999px;
  flex-shrink: 0;
}

.decision-panel-badge-muted {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  padding: 4px 10px;
  border-radius: 999px;
  flex-shrink: 0;
}

.decision-panel-hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
}

.copy-hint {
  margin: 0 0 12px;
  font-size: 12px;
  font-weight: 600;
  color: #166534;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  padding: 8px 10px;
  border-radius: 8px;
}

.copy-hint--error {
  color: #991b1b;
  background: #fef2f2;
  border-color: #fecaca;
}

.scope-page-note-section {
  margin-bottom: 14px;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid #c7d2fe;
  background: #eef2ff;
}

.decision-panel--compact .scope-page-note-section {
  padding: 10px;
  margin-bottom: 10px;
}

.scope-page-note-title {
  margin: 0 0 4px;
  font-size: 12px;
  font-weight: 800;
  color: #3730a3;
}

.scope-page-note-desc {
  margin: 0 0 8px;
  font-size: 11px;
  color: #6366f1;
}

.scope-code {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #e0e7ff;
  color: #312e81;
}

.scope-page-note-textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #a5b4fc;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  font-family: inherit;
  line-height: 1.45;
  resize: vertical;
  min-height: 72px;
  background: #fff;
}

.scope-page-note-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.btn-scope-save,
.btn-scope-copy {
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid transparent;
}

.btn-scope-save {
  background: #4f46e5;
  color: #fff;
  border-color: #4338ca;
}

.btn-scope-save:hover {
  background: #4338ca;
}

.btn-scope-copy {
  background: #fff;
  color: #4338ca;
  border-color: #a5b4fc;
}

.btn-scope-copy:hover {
  background: #e0e7ff;
}

.scope-page-note-feedback {
  font-size: 11px;
  font-weight: 700;
  color: #15803d;
}

.scope-page-note-saved-at {
  font-size: 10px;
  color: #64748b;
}

.decision-panel-list {
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.export-section {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed #cbd5e1;
}

.export-title {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.export-desc {
  margin: 0 0 10px;
  font-size: 11px;
  color: #64748b;
  line-height: 1.4;
}

.export-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.btn-export {
  border: 1px solid #2563eb;
  background: #2563eb;
  color: #fff;
  border-radius: 8px;
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.btn-export:hover {
  background: #1d4ed8;
}

.btn-export-secondary {
  background: #fff;
  color: #1d4ed8;
}

.btn-export-secondary:hover {
  background: #eff6ff;
}
</style>
