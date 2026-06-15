import { defineStore } from "pinia";

export type FeEvaluatorRole = "MANAGER" | "TEAM_LEADER" | null;
export type TeamLeaderPhase = "evaluate" | "report" | "results" | null;

/** 현장 기능인제 — 레이아웃·단계 UI 공유 */
export const useFeSiteSessionStore = defineStore("feSiteSession", {
  state: () => ({
    evaluatorRole: null as FeEvaluatorRole,
    teamLeaderPhase: null as TeamLeaderPhase,
  }),
  getters: {
    isTeamLeader: (s) => s.evaluatorRole === "TEAM_LEADER",
  },
  actions: {
    setEvaluatorRole(role: FeEvaluatorRole) {
      this.evaluatorRole = role;
    },
    setTeamLeaderPhase(phase: TeamLeaderPhase) {
      this.teamLeaderPhase = phase;
    },
    reset() {
      this.evaluatorRole = null;
      this.teamLeaderPhase = null;
    },
  },
});
