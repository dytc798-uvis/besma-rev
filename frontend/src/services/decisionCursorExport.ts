import type { DecisionAction, DecisionLogRecord, DecisionRecord } from "@/services/decisionService";

/** 승인 건만 Cursor 즉시 실행 대상 */
export function executionReady(action: DecisionAction): boolean {
  return action === "APPROVED";
}

/** 모호한 실행 지시 차단 (승인 시) */
export function isVagueImplementationInstruction(text: string): boolean {
  const t = text.trim();
  if (!t) return true;
  const vague = [
    /추후\s*구현/i,
    /구현\s*예정/i,
    /\bTBD\b/i,
    /\bto\s*be\s*determined\b/i,
    /추가\s*예정/i,
    /후속\s*구현/i,
  ];
  return vague.some((re) => re.test(t));
}

/**
 * 처리 후 클립보드·Export용: note(구현 지시) 기반 Cursor 실행 블록
 */
export function formatCursorExecutionMarkdown(p: {
  decision_id: string;
  scope: string;
  action: DecisionAction;
  /** 구현 지시 본문 (= note) */
  implementation_instruction: string;
}): string {
  const body = p.implementation_instruction?.trim() || "(구현 지시 없음)";

  return [
    "### Cursor 실행 지시",
    "",
    `- decision_id: ${p.decision_id}`,
    `- scope: ${p.scope}`,
    `- action: ${p.action}`,
    "",
    "구현 내용:",
    body,
    "",
    "구현 조건:",
    "- 기존 기능 유지",
    "- 기존 API 구조 변경 금지",
    "- UI만 수정 또는 필요한 최소 기능 추가",
    "",
  ].join("\n");
}

/** 미결정 항목 없이 scope(화면)별로 남기는 요청·의도 */
export function formatScopePageIntentMarkdown(p: {
  scope: string;
  text: string;
  updated_at?: string;
}): string {
  const body = p.text?.trim() || "(내용 없음)";
  const lines = [
    "### 페이지 표현 (scope 메모)",
    "",
    `- **scope**: \`${p.scope}\``,
    ...(p.updated_at ? [`- **기록 시각**: ${p.updated_at}`] : []),
    "",
    "내용:",
    body,
    "",
    "_미결정 Decision 항목과 별도로, 이 화면에 남긴 요청·의도입니다. Cursor에 붙여 공유·구현 참고용으로 사용할 수 있습니다._",
    "",
  ];
  return lines.join("\n");
}

export type ReviewDecisionAction = "PENDING";

export function formatReviewDraftMarkdown(p: {
  decision_id: string;
  scope: string;
  title: string;
  selected_option: string;
  /** 구현 지시(초안) — 승인 시 그대로 Cursor 실행 블록에 실림 */
  note: string;
  /** 선택지에 연결된 참고용 구현 힌트 */
  implementation_directive: string;
}): string {
  const noteLine = p.note?.trim() ? p.note.trim() : "(아직 없음 — 승인 전에 반드시 작성)";
  const dir = p.implementation_directive?.trim() || "(선택지에 구현 힌트 미정의)";

  return [
    "### Decision 검토안 (확정 아님)",
    "",
    "_검토·공유용입니다. **실제 구현**에는 승인/보류/기각 후 자동 복사되는 「**Cursor 실행 지시**」블록을 Cursor에 붙여 사용하세요._",
    "",
    `- **decision_id**: \`${p.decision_id}\``,
    `- **scope**: \`${p.scope}\``,
    `- **title**: ${p.title}`,
    `- **검토 중인 선택안**: ${p.selected_option}`,
    `- **구현 지시 (초안)**: ${noteLine}`,
    "",
    "#### 선택지 참고 힌트 (옵션별)",
    "",
    dir,
    "",
  ].join("\n");
}

/** 로그에서 Export용: note 기반 Cursor 실행 블록 (JSON의 cursor_execution_markdown 등에 동일 사용) */
export function cursorExecutionMarkdownFromLog(log: DecisionLogRecord): string {
  return formatCursorExecutionMarkdown({
    decision_id: log.decision_id,
    scope: log.scope,
    action: log.action,
    implementation_instruction: log.note,
  });
}

/** 로그에 title 이 없을 때(구버전) items 에서 보강 */
export function attachTitlesToLogs(
  logs: DecisionLogRecord[],
  items: DecisionRecord[],
): DecisionLogRecord[] {
  const titles = new Map(items.map((d) => [d.id, d.title]));
  return logs.map((l) => ({
    ...l,
    title: l.title ?? titles.get(l.decision_id) ?? "",
  }));
}

export function exportAllLogsMarkdown(logs: DecisionLogRecord[]): string {
  const ts = new Date().toISOString();
  const blocks = logs.map((log) => cursorExecutionMarkdownFromLog(log).trimEnd());
  const body = blocks.join("\n\n---\n\n");
  return `# BESMA Decision Export (Markdown)\n\ngenerated: ${ts}\nentries: ${logs.length}\n\n---\n\n${body}\n`;
}

export function exportAllLogsJson(logs: DecisionLogRecord[]): string {
  const ts = new Date().toISOString();
  const entries = logs.map((log) => ({
    decision_id: log.decision_id,
    scope: log.scope,
    title: log.title ?? "",
    action: log.action,
    selected_option: log.selected_option,
    note: log.note ?? "",
    implementation_instruction: log.note ?? "",
    execution_ready: executionReady(log.action),
    implementation_directive: log.implementation_directive ?? "",
    cursor_execution_markdown: cursorExecutionMarkdownFromLog(log),
    resolved_at: log.resolved_at,
    log_id: log.id,
  }));
  return JSON.stringify({ generated: ts, entries }, null, 2);
}

export async function copyTextToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}

export function downloadTextFile(filename: string, content: string, mime = "text/plain") {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
