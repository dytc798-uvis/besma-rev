<template>
  <section class="ops-card">
    <h2>④ TBM 운영 / 서명 현황</h2>
    <p v-if="!distributionId" class="msg hint">
      현재 작업 시나리오의 배포가 아직 없습니다. ③ 배포 생성 후 여기에서 TBM을 운영하세요.
    </p>

    <div v-if="recentDistributions.length > 0" class="recent-box">
      <strong>최근 배포 이력 (수동 불러오기)</strong>
      <div class="recent-grid">
        <button
          v-for="d in recentDistributions"
          :key="d.id"
          class="btn-secondary btn-small"
          :class="{ active: d.id === distributionId }"
          @click="$emit('select-distribution', d.id)"
        >
          #{{ d.id }} / {{ d.target_date }} / {{ d.is_reassignment ? "재지시" : "일반" }} / {{ d.is_tbm_active ? "TBM시작" : "미시작" }} / {{ d.worker_count }}명
        </button>
      </div>
    </div>

    <template v-if="distribution">
      <div class="status-grid">
        <div><strong>배포:</strong> #{{ distribution.id }}</div>
        <div><strong>TBM:</strong> {{ distribution.is_tbm_active ? "시작됨" : "미시작" }}</div>
        <div><strong>TBM 시작:</strong> {{ distribution.tbm_started_at ?? "-" }}</div>
        <div><strong>대상:</strong> {{ stats.total }}명</div>
        <div><strong>시작 서명:</strong> {{ stats.startSigned }}명</div>
        <div><strong>종료 서명:</strong> {{ stats.endSigned }}명</div>
        <div><strong>ISSUE:</strong> {{ stats.issueCount }}건</div>
      </div>

      <p v-if="distribution.is_reassignment" class="reassign-chip">
        작업 변경 재지시 배포입니다. 사유: {{ distribution.reassignment_reason ?? "-" }}
      </p>

      <div class="action-row">
        <button
          class="btn-primary"
          :disabled="loading || distribution.is_tbm_active"
          @click="startTbm"
        >
          {{ distribution.is_tbm_active ? "TBM 이미 시작됨" : "TBM 시작" }}
        </button>
        <button class="btn-secondary" :disabled="loading" @click="pingPresence">
          관리자 위치 Ping
        </button>
        <button class="btn-secondary" :disabled="loading" @click="refreshAll">
          새로고침
        </button>
      </div>
      <p class="msg hint">근로자 안내: 문자 또는 QR로 `/worker/mobile?access_token=...` 링크 전달</p>

      <p v-if="message" :class="['msg', msgType]">{{ message }}</p>

      <div v-if="distribution.workers?.length" class="worker-list">
        <div class="worker-list-header">근로자 서명 현황 / 재지시 대상 선택</div>
        <div v-for="w in distribution.workers" :key="w.id" class="worker-status-row">
          <label class="worker-selector">
            <input type="checkbox" :value="w.person_id" v-model="selectedWorkerIds" />
          </label>
          <div class="worker-name">
            <strong>{{ w.person_name ?? `person #${w.person_id}` }}</strong>
            <span class="ack-badge" :class="w.ack_status?.toLowerCase()">{{ w.ack_status }}</span>
          </div>
          <div class="worker-times">
            <span>시작: {{ w.start_signed_at ?? "-" }}</span>
            <span>종료: {{ w.end_signed_at ?? "-" }}</span>
            <span v-if="w.issue_flag" class="issue-flag">ISSUE</span>
          </div>
          <div class="worker-link-actions">
            <button class="btn-text" @click="copyWorkerLink(w.access_token)">링크 복사</button>
          </div>
        </div>
      </div>

      <section class="subsection">
        <div class="subsection-header">
          <strong>근로자 피드백 검토</strong>
          <button class="btn-secondary btn-small" :disabled="feedbackLoading" @click="loadFeedbacks">
            {{ feedbackLoading ? "조회 중..." : "목록 새로고침" }}
          </button>
        </div>
        <div v-if="feedbacks.length === 0" class="msg hint">등록된 피드백이 없습니다.</div>
        <div v-for="feedback in feedbacks" :key="feedback.id" class="feedback-card">
          <div class="feedback-meta">
            <strong>{{ feedback.person_name ?? `person #${feedback.person_id}` }}</strong>
            <span>{{ feedback.feedback_type }}</span>
            <span>{{ feedback.created_at }}</span>
            <span class="ack-badge" :class="feedback.status">{{ feedback.status }}</span>
            <span v-if="feedback.candidate_status">후보 {{ feedback.candidate_status }}</span>
          </div>
          <div class="feedback-content">{{ feedback.content }}</div>
          <div class="feedback-actions">
            <button class="btn-secondary btn-small" :disabled="loading" @click="reviewFeedback(feedback.id, 'approved')">승인</button>
            <button class="btn-secondary btn-small" :disabled="loading" @click="reviewFeedback(feedback.id, 'rejected')">반려</button>
            <button class="btn-secondary btn-small" :disabled="loading" @click="promoteFeedback(feedback.id)">자산화 후보 생성</button>
          </div>
        </div>
      </section>

      <section class="subsection">
        <div class="subsection-header">
          <strong>작업 변경 재지시</strong>
          <span class="helper-inline">선택 근로자 {{ selectedWorkerIds.length }}명</span>
        </div>

        <div class="field-row">
          <label>새 작업명</label>
          <input v-model="reassignWorkName" type="text" placeholder="예: 천장 배관 보강" />
        </div>
        <div class="field-row">
          <label>작업내용</label>
          <textarea v-model="reassignWorkDescription" rows="3" placeholder="변경된 작업 내용과 주의사항을 입력하세요." />
        </div>
        <div class="field-row">
          <label>팀 라벨</label>
          <input v-model="reassignTeamLabel" type="text" placeholder="선택사항" />
        </div>
        <div class="field-row">
          <label>변경 사유</label>
          <textarea v-model="reassignReason" rows="2" placeholder="왜 재지시가 필요한지 기록합니다." />
        </div>

        <div class="field-row">
          <label>위험 검색</label>
          <input v-model="riskQuery" type="text" placeholder="배관, 감전, 추락 등으로 검색" />
          <button class="btn-secondary btn-small" :disabled="riskLoading || !riskQuery.trim()" @click="searchRisks">
            {{ riskLoading ? "검색 중..." : "검색" }}
          </button>
        </div>

        <div v-if="riskResults.length > 0" class="risk-select-list">
          <label v-for="risk in riskResults" :key="risk.risk_revision_id" class="risk-select-row">
            <input type="checkbox" :value="risk.risk_revision_id" v-model="selectedRiskRevisionIds" />
            <span>
              <strong>{{ risk.risk_factor }}</strong>
              <small>{{ risk.counterplan }}</small>
            </span>
          </label>
        </div>

        <button
          class="btn-primary"
          :disabled="loading || selectedWorkerIds.length === 0 || !reassignWorkName.trim() || !reassignWorkDescription.trim() || !reassignReason.trim()"
          @click="createReassignment"
        >
          작업 변경 재배포 실행
        </button>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

interface DistWorker {
  id: number;
  person_id: number;
  person_name?: string;
  access_token: string;
  ack_status: string;
  start_signed_at: string | null;
  end_signed_at: string | null;
  issue_flag: boolean;
}

interface DistDetail {
  id: number;
  site_id: number;
  is_tbm_active: boolean;
  tbm_started_at: string | null;
  is_reassignment?: boolean;
  reassignment_reason?: string | null;
  workers: DistWorker[];
}

interface DistSummary {
  id: number;
  target_date: string;
  is_tbm_active: boolean;
  is_reassignment?: boolean;
  worker_count: number;
}

interface FeedbackItem {
  id: number;
  person_id: number;
  person_name?: string | null;
  feedback_type: string;
  content: string;
  created_at: string;
  status: string;
  candidate_status?: string | null;
}

interface RiskSearchItem {
  risk_revision_id: number;
  risk_factor: string;
  counterplan: string;
}

const props = defineProps<{
  distributionId: number | null;
  distribution: DistDetail | null;
  recentDistributions: DistSummary[];
  siteId: number;
}>();
const emit = defineEmits<{
  (e: "select-distribution", id: number): void;
  (e: "refresh-distribution"): void;
  (e: "tbm-started"): void;
}>();

const auth = useAuthStore();
const loading = ref(false);
const feedbackLoading = ref(false);
const riskLoading = ref(false);
const message = ref("");
const msgType = ref<"success" | "error">("success");
const feedbacks = ref<FeedbackItem[]>([]);
const selectedWorkerIds = ref<number[]>([]);
const reassignWorkName = ref("");
const reassignWorkDescription = ref("");
const reassignTeamLabel = ref("");
const reassignReason = ref("");
const riskQuery = ref("");
const riskResults = ref<RiskSearchItem[]>([]);
const selectedRiskRevisionIds = ref<number[]>([]);

const stats = computed(() => {
  const workers = props.distribution?.workers ?? [];
  return {
    total: workers.length,
    startSigned: workers.filter((w) => !!w.start_signed_at).length,
    endSigned: workers.filter((w) => !!w.end_signed_at).length,
    issueCount: workers.filter((w) => w.issue_flag).length,
  };
});

function setMsg(text: string, type: "success" | "error") {
  message.value = text;
  msgType.value = type;
}

async function startTbm() {
  if (!props.distributionId) return;
  loading.value = true;
  try {
    await api.post(`/daily-work-plans/distributions/${props.distributionId}/start-tbm`);
    setMsg("TBM 시작 완료", "success");
    emit("tbm-started");
    emit("refresh-distribution");
  } catch (err: any) {
    setMsg(err?.response?.data?.detail ?? "TBM 시작 실패", "error");
  } finally {
    loading.value = false;
  }
}

async function pingPresence() {
  loading.value = true;
  try {
    const siteId = props.siteId || auth.effectiveSiteId;
    if (!siteId) throw new Error("site context가 없습니다.");
    let lat: number | null = null;
    let lng: number | null = null;
    if (navigator.geolocation && window.isSecureContext) {
      try {
        const pos = await new Promise<GeolocationPosition>((resolve, reject) =>
          navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: true,
            timeout: 5000,
          }),
        );
        lat = pos.coords.latitude;
        lng = pos.coords.longitude;
      } catch {
        /* fallback to null */
      }
    }
    await api.post("/daily-work-plans/admin-presence/ping", { site_id: siteId, lat, lng });
    setMsg("관리자 위치 ping 완료", "success");
  } catch (err: any) {
    setMsg(err?.response?.data?.detail ?? err?.message ?? "ping 실패", "error");
  } finally {
    loading.value = false;
  }
}

async function copyWorkerLink(token: string) {
  const link = `${window.location.origin}/worker/mobile?access_token=${encodeURIComponent(token)}`;
  try {
    await navigator.clipboard.writeText(link);
    setMsg("근로자 접속 링크를 복사했습니다.", "success");
  } catch {
    setMsg("클립보드 복사에 실패했습니다.", "error");
  }
}

async function loadFeedbacks() {
  if (!props.distributionId) return;
  feedbackLoading.value = true;
  try {
    const res = await api.get(`/daily-work-plans/distributions/${props.distributionId}/feedbacks`);
    feedbacks.value = res.data ?? [];
  } catch {
    feedbacks.value = [];
  } finally {
    feedbackLoading.value = false;
  }
}

async function reviewFeedback(feedbackId: number, status: "approved" | "rejected") {
  loading.value = true;
  try {
    await api.post(`/feedbacks/${feedbackId}/review`, {
      status,
      review_note: status === "approved" ? "현장 검토 승인" : "현장 검토 반려",
    });
    setMsg(`피드백 ${status === "approved" ? "승인" : "반려"} 처리 완료`, "success");
    await loadFeedbacks();
  } catch (err: any) {
    setMsg(err?.response?.data?.detail ?? "피드백 검토 실패", "error");
  } finally {
    loading.value = false;
  }
}

async function promoteFeedback(feedbackId: number) {
  loading.value = true;
  try {
    await api.post(`/feedbacks/${feedbackId}/promote-candidate`);
    setMsg("위험성평가 DB 후보로 적재했습니다.", "success");
    await loadFeedbacks();
  } catch (err: any) {
    setMsg(err?.response?.data?.detail ?? "후보 자산화 실패", "error");
  } finally {
    loading.value = false;
  }
}

async function searchRisks() {
  if (!riskQuery.value.trim()) return;
  riskLoading.value = true;
  try {
    const res = await api.get("/search/risk-library", {
      params: {
        query: riskQuery.value.trim(),
        mode: "quick",
        limit: 10,
      },
    });
    riskResults.value = (res.data?.results ?? []).map((item: any) => ({
      risk_revision_id: item.risk_revision_id,
      risk_factor: item.risk_factor,
      counterplan: item.counterplan,
    }));
  } catch {
    riskResults.value = [];
  } finally {
    riskLoading.value = false;
  }
}

async function createReassignment() {
  if (!props.distributionId) return;
  loading.value = true;
  try {
    const res = await api.post(
      `/daily-work-plans/distributions/${props.distributionId}/reassign-workers`,
      {
        person_ids: selectedWorkerIds.value,
        new_work_name: reassignWorkName.value.trim(),
        new_work_description: reassignWorkDescription.value.trim(),
        team_label: reassignTeamLabel.value.trim() || null,
        selected_risk_revision_ids: selectedRiskRevisionIds.value,
        reason: reassignReason.value.trim(),
      },
    );
    setMsg(`재지시 배포 #${res.data.reassignment_distribution_id} 생성 완료`, "success");
    emit("select-distribution", res.data.reassignment_distribution_id);
    selectedRiskRevisionIds.value = [];
    selectedWorkerIds.value = [];
    reassignWorkName.value = "";
    reassignWorkDescription.value = "";
    reassignTeamLabel.value = "";
    reassignReason.value = "";
    riskResults.value = [];
  } catch (err: any) {
    setMsg(err?.response?.data?.detail ?? "재지시 배포 생성 실패", "error");
  } finally {
    loading.value = false;
  }
}

async function refreshAll() {
  emit("refresh-distribution");
  await loadFeedbacks();
}

watch(
  () => props.distributionId,
  (value) => {
    feedbacks.value = [];
    selectedWorkerIds.value = [];
    if (value) {
      loadFeedbacks();
    }
  },
  { immediate: true },
);
</script>

<style scoped>
.subsection {
  margin-top: 16px;
  border-top: 1px solid #e5e7eb;
  padding-top: 12px;
}

.subsection-header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.helper-inline {
  color: #64748b;
  font-size: 13px;
}

.worker-selector {
  display: flex;
  align-items: center;
}

.feedback-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 10px;
  background: #fafafa;
}

.feedback-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}

.feedback-content {
  margin-bottom: 8px;
  white-space: pre-wrap;
}

.feedback-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.risk-select-list {
  display: grid;
  gap: 8px;
  margin-bottom: 10px;
}

.risk-select-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
}

.risk-select-row span {
  display: grid;
  gap: 4px;
}

.risk-select-row small {
  color: #64748b;
}

.reassign-chip {
  margin: 10px 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff7ed;
  color: #9a3412;
}

textarea {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px;
  font-size: 14px;
  resize: vertical;
}
</style>
