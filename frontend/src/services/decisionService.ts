import { ref } from "vue";
import decisionsFile from "@/data/decisions.json";
import decisionLogFile from "@/data/decision_log.json";
import { formatCursorExecutionMarkdown, isVagueImplementationInstruction } from "@/services/decisionCursorExport";

export type DecisionAction = "APPROVED" | "DEFERRED" | "REJECTED";
export type DecisionStatus = "open" | "approved" | "deferred" | "rejected";

/** UI·로그용: id는 감사 추적용(화면에 노출하지 않음), label/description이 운영자용 본문 */
export interface DecisionOption {
  id: string;
  label: string;
  description: string;
  recommended?: boolean;
  /** 선택 시 즉시 보여 줄 예상 반영 결과 */
  expectedOutcome?: string;
  /** 확정 반영 시 Cursor/개발자용 구체 지시 (파일·KPI·정렬·필터 등) */
  implementationDirective?: string;
}

export interface DecisionRecord {
  id: string;
  scope: string;
  status: DecisionStatus;
  title: string;
  summary?: string;
  refDoc?: string;
  /** 설명형 의사결정 선택지 (없으면 컴포넌트 기본안 사용) */
  options?: DecisionOption[];
  resolved_at?: string;
  resolved_by?: string;
  selected_option?: string;
}

export interface DecisionLogRecord {
  id: string;
  decision_id: string;
  /** Export·Cursor용 (처리 시점 스냅샷) */
  title?: string;
  action: DecisionAction;
  selected_option: string;
  /** 선택지의 구체 구현 힌트 스냅샷(참고) */
  implementation_directive?: string;
  resolved_at: string;
  scope: string;
  /**
   * 구현 지시 (implementation instruction).
   * 승인 시 Cursor 실행 블록의 본문으로 그대로 사용됨.
   */
  note: string;
}

interface DecisionsFile {
  version: number;
  items: DecisionRecord[];
}

interface DecisionLogFile {
  version: number;
  items: DecisionLogRecord[];
}

const file = decisionsFile as DecisionsFile;
const logFile = decisionLogFile as DecisionLogFile;

/** localStorage 키 (요구사항 고정) */
const STORAGE_DECISIONS = "besma_decisions";
const STORAGE_DECISION_LOG = "besma_decision_log";
const STORAGE_SCOPE_PAGE_NOTES = "besma_scope_page_notes";

interface ScopePageNotesFile {
  version: number;
  byScope: Record<string, { text: string; updated_at: string }>;
}

function normalizeScopePageNotesByScope(
  raw: unknown,
): Record<string, { text: string; updated_at: string }> {
  if (!raw || typeof raw !== "object") return {};
  const out: Record<string, { text: string; updated_at: string }> = {};
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (!v || typeof v !== "object") continue;
    const o = v as { text?: unknown; updated_at?: unknown };
    if (typeof o.text !== "string") continue;
    out[k] = {
      text: o.text,
      updated_at: typeof o.updated_at === "string" ? o.updated_at : new Date().toISOString(),
    };
  }
  return out;
}

function parseStoredScopePageNotes(raw: string | null): ScopePageNotesFile | null {
  if (raw == null || raw === "") return null;
  try {
    const o = JSON.parse(raw) as unknown;
    if (!o || typeof o !== "object") return null;
    const v = o as ScopePageNotesFile;
    if (typeof v.version !== "number" || v.byScope == null || typeof v.byScope !== "object") return null;
    return { version: v.version, byScope: normalizeScopePageNotesByScope(v.byScope) };
  } catch {
    return null;
  }
}

function loadInitialScopePageNotes(): { version: number; byScope: Record<string, { text: string; updated_at: string }> } {
  if (typeof localStorage === "undefined") {
    return { version: 1, byScope: {} };
  }
  const parsed = parseStoredScopePageNotes(localStorage.getItem(STORAGE_SCOPE_PAGE_NOTES));
  if (parsed) {
    return { version: parsed.version, byScope: { ...parsed.byScope } };
  }
  return { version: 1, byScope: {} };
}

function hasLocalStorage(): boolean {
  return typeof localStorage !== "undefined";
}

function parseStoredDecisions(raw: string | null): DecisionsFile | null {
  if (raw == null || raw === "") return null;
  try {
    const o = JSON.parse(raw) as unknown;
    if (!o || typeof o !== "object") return null;
    const v = o as DecisionsFile;
    if (typeof v.version !== "number" || !Array.isArray(v.items)) return null;
    return v;
  } catch {
    return null;
  }
}

function parseStoredLogs(raw: string | null): DecisionLogFile | null {
  if (raw == null || raw === "") return null;
  try {
    const o = JSON.parse(raw) as unknown;
    if (!o || typeof o !== "object") return null;
    const v = o as DecisionLogFile;
    if (typeof v.version !== "number" || !Array.isArray(v.items)) return null;
    return v;
  } catch {
    return null;
  }
}

/** 초기 로드: localStorage 우선, 없거나 파싱 실패 시 번들 JSON fallback */
function loadInitialDecisions(): DecisionsFile {
  if (!hasLocalStorage()) {
    return {
      version: file.version,
      items: Array.isArray(file.items) ? [...file.items] : [],
    };
  }
  const parsed = parseStoredDecisions(localStorage.getItem(STORAGE_DECISIONS));
  if (parsed) {
    return { version: parsed.version, items: [...parsed.items] };
  }
  return {
    version: file.version,
    items: Array.isArray(file.items) ? [...file.items] : [],
  };
}

function loadInitialLogs(): DecisionLogFile {
  if (!hasLocalStorage()) {
    return {
      version: logFile.version,
      items: Array.isArray(logFile.items) ? [...logFile.items] : [],
    };
  }
  const parsed = parseStoredLogs(localStorage.getItem(STORAGE_DECISION_LOG));
  if (parsed) {
    return { version: parsed.version, items: [...parsed.items] };
  }
  return {
    version: logFile.version,
    items: Array.isArray(logFile.items) ? [...logFile.items] : [],
  };
}

const initialDecisions = loadInitialDecisions();
const initialLogs = loadInitialLogs();
const initialScopePageNotes = loadInitialScopePageNotes();

/** 저장 시 유지할 version 필드 (최초 로드 출처 기준) */
let decisionsPersistVersion = initialDecisions.version;
let logPersistVersion = initialLogs.version;
let scopePageNotesPersistVersion = initialScopePageNotes.version;

const decisionItems = ref<DecisionRecord[]>(initialDecisions.items);
const decisionLogs = ref<DecisionLogRecord[]>(initialLogs.items);
/** scope(화면)별 자유 메모 — 미결정 항목이 없어도 표현 가능 */
const scopePageNotesByScope = ref<Record<string, { text: string; updated_at: string }>>(
  initialScopePageNotes.byScope,
);

function persistScopePageNotesToLocalStorage(): void {
  if (!hasLocalStorage()) return;
  try {
    const payload: ScopePageNotesFile = {
      version: scopePageNotesPersistVersion,
      byScope: scopePageNotesByScope.value,
    };
    localStorage.setItem(STORAGE_SCOPE_PAGE_NOTES, JSON.stringify(payload));
  } catch (e) {
    console.warn("[decisionService] scope 페이지 메모 localStorage 저장 실패:", e);
  }
}

/** 이 화면(scope)에 남긴 요청·의도 저장 (빈 문자열이면 해당 scope 항목 삭제) */
export function saveScopePageNote(scope: string, text: string): void {
  const t = text.trim();
  const next = { ...scopePageNotesByScope.value };
  if (!t) {
    delete next[scope];
  } else {
    next[scope] = { text: t, updated_at: new Date().toISOString() };
  }
  scopePageNotesByScope.value = next;
  persistScopePageNotesToLocalStorage();
}

export function getScopePageNotesRef() {
  return scopePageNotesByScope;
}

/**
 * 현재 decisions / decision_log 스냅샷을 localStorage에 기록.
 * resolveDecision 성공 시 호출.
 */
function persistDecisionStateToLocalStorage(): void {
  if (!hasLocalStorage()) return;
  try {
    const decisionsPayload: DecisionsFile = {
      version: decisionsPersistVersion,
      items: decisionItems.value,
    };
    const logsPayload: DecisionLogFile = {
      version: logPersistVersion,
      items: decisionLogs.value,
    };
    localStorage.setItem(STORAGE_DECISIONS, JSON.stringify(decisionsPayload));
    localStorage.setItem(STORAGE_DECISION_LOG, JSON.stringify(logsPayload));
  } catch (e) {
    console.warn("[decisionService] localStorage 저장 실패:", e);
  }
}

const CURRENT_USER = "ui_operator";

function mapActionToStatus(action: DecisionAction): DecisionStatus {
  if (action === "APPROVED") return "approved";
  if (action === "DEFERRED") return "deferred";
  return "rejected";
}

function makeLogId(): string {
  return `log-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function getDecisionItemsRef() {
  return decisionItems;
}

export function getDecisionLogsRef() {
  return decisionLogs;
}

export function getAllDecisionItems(): DecisionRecord[] {
  return decisionItems.value;
}

export function getOpenDecisionsForScope(scope: string): DecisionRecord[] {
  return decisionItems.value.filter((d) => d.scope === scope && d.status === "open");
}

export function getOpenCountByScopeMap(): Record<string, number> {
  const map: Record<string, number> = {};
  for (const d of decisionItems.value) {
    if (d.status !== "open") continue;
    map[d.scope] = (map[d.scope] ?? 0) + 1;
  }
  return map;
}

export function getTotalOpenCount(): number {
  return decisionItems.value.filter((d) => d.status === "open").length;
}

export type ResolveDecisionFailureReason = "NOT_FOUND" | "EMPTY_APPROVAL_INSTRUCTION" | "VAGUE_APPROVAL_INSTRUCTION";

export function resolveDecision(
  decisionId: string,
  action: DecisionAction,
  selectedOption: string,
  note = "",
  implementationDirective = "",
): {
  ok: true;
  decision: DecisionRecord;
  log: DecisionLogRecord;
  cursor_execution_markdown: string;
} | { ok: false; reason: ResolveDecisionFailureReason } {
  const idx = decisionItems.value.findIndex((d) => d.id === decisionId);
  if (idx < 0) return { ok: false as const, reason: "NOT_FOUND" };

  const trimmedNote = note.trim();
  if (action === "APPROVED") {
    if (!trimmedNote) {
      return { ok: false as const, reason: "EMPTY_APPROVAL_INSTRUCTION" };
    }
    if (isVagueImplementationInstruction(trimmedNote)) {
      return { ok: false as const, reason: "VAGUE_APPROVAL_INSTRUCTION" };
    }
  }

  const nowIso = new Date().toISOString();
  const nextStatus = mapActionToStatus(action);
  const target = decisionItems.value[idx];

  decisionItems.value[idx] = {
    ...target,
    status: nextStatus,
    resolved_at: nowIso,
    resolved_by: CURRENT_USER,
    selected_option: selectedOption,
  };

  const log: DecisionLogRecord = {
    id: makeLogId(),
    decision_id: decisionId,
    title: target.title,
    action,
    selected_option: selectedOption,
    implementation_directive: implementationDirective.trim(),
    resolved_at: nowIso,
    scope: target.scope,
    note: note.trim(),
  };
  decisionLogs.value = [log, ...decisionLogs.value];

  const cursor_execution_markdown = formatCursorExecutionMarkdown({
    decision_id: decisionId,
    scope: target.scope,
    action,
    implementation_instruction: log.note,
  });

  persistDecisionStateToLocalStorage();

  return { ok: true as const, decision: decisionItems.value[idx], log, cursor_execution_markdown };
}
