import { computed } from "vue";
import {
  getDecisionItemsRef,
  getDecisionLogsRef,
  getOpenCountByScopeMap,
  getOpenDecisionsForScope,
  getScopePageNotesRef,
  resolveDecision,
  saveScopePageNote,
  type DecisionAction,
  type DecisionRecord,
} from "@/services/decisionService";

export function useDecisionState() {
  const decisionItems = getDecisionItemsRef();
  const decisionLogs = getDecisionLogsRef();
  const scopePageNotesByScope = getScopePageNotesRef();
  const openCountByScope = computed(() => getOpenCountByScopeMap());

  function openCountForScope(scope: string): number {
    return openCountByScope.value[scope] ?? 0;
  }

  function openDecisionsForScope(scope: string): DecisionRecord[] {
    return getOpenDecisionsForScope(scope);
  }

  function resolve(
    decisionId: string,
    action: DecisionAction,
    selectedOption: string,
    note = "",
    implementationDirective = "",
  ) {
    return resolveDecision(decisionId, action, selectedOption, note, implementationDirective);
  }

  return {
    decisionItems,
    decisionLogs,
    scopePageNotesByScope,
    saveScopePageNote,
    openCountByScope,
    openCountForScope,
    openDecisionsForScope,
    resolveDecision: resolve,
  };
}
