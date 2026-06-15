import { defineStore } from "pinia";
import type { FeNavRoleCache } from "@/utils/feSessionCache";
import { readNavRoleCached, writeNavRoleCached } from "@/utils/feSessionCache";

export type FeEvaluatorRole = "MANAGER" | "TEAM_LEADER" | null;
export type TeamLeaderPhase = "evaluate" | "report" | "results" | null;

/** 현장 기능인제 — 레이아웃·단계 UI 공유 */
export const useFeSiteSessionStore = defineStore("feSiteSession", {
  state: () => ({
    evaluatorRole: null as FeEvaluatorRole,
    teamLeaderPhase: null as TeamLeaderPhase,
    /** my-site/workers 최초 로드 후 true — 메뉴 깜빡임 방지 */
    navHydrated: false,
  }),
  getters: {
    isTeamLeader: (s) => s.evaluatorRole === "TEAM_LEADER",
  },
  actions: {
    hydrateNavFromCache(loginId: string) {
      const cached = readNavRoleCached(loginId);
      if (!cached) return;
      this.evaluatorRole = cached;
      this.navHydrated = true;
    },
    syncFromSite(
      evaluatorRole: FeEvaluatorRole,
      teamLeaderPhase: TeamLeaderPhase,
      loginId?: string | null,
    ) {
      this.evaluatorRole = evaluatorRole;
      this.teamLeaderPhase = teamLeaderPhase;
      this.navHydrated = true;
      if (loginId && evaluatorRole) {
        writeNavRoleCached(loginId, evaluatorRole as FeNavRoleCache);
      }
    },
    setEvaluatorRole(role: FeEvaluatorRole) {
      this.evaluatorRole = role;
    },
    setTeamLeaderPhase(phase: TeamLeaderPhase) {
      this.teamLeaderPhase = phase;
    },
    reset() {
      this.evaluatorRole = null;
      this.teamLeaderPhase = null;
      this.navHydrated = false;
    },
  },
});
