<template>
  <div class="fe-evidence-page" :class="{ 'is-loading': loading }">
    <header class="page-head">
      <div>
        <h1 class="page-title">기능인정제 안전보건실 승인 및 포상/제재</h1>
        <p class="page-sub">완료 현장 안전보건실 승인, 포상·제재 증빙을 한 화면에서 확인합니다.</p>
      </div>
      <button class="stitch-btn-secondary" type="button" :disabled="loading" @click="loadQueues">
        {{ loading ? "조회 중..." : "새로고침" }}
      </button>
    </header>

    <div v-if="loading" class="loading-overlay" role="status" aria-live="polite">
      <div class="loading-card">
        <span class="loading-spinner" aria-hidden="true"></span>
        <strong>승인 대기 목록을 불러오는 중입니다.</strong>
        <small>담당 검토, 포상, 제재 대기 건을 확인하고 있습니다.</small>
      </div>
    </div>

    <p v-if="loadError" class="load-error" role="alert">{{ loadError }}</p>

    <section class="evidence-summary">
      <div class="summary-card--primary">
        <span>총 승인 대기</span>
        <strong>{{ totalPendingCount }}</strong>
      </div>
      <div>
        <span>담당 검토 대기</span>
        <strong>{{ hqApprovalRows.length }}</strong>
      </div>
      <div>
        <span>포상 사진 증빙</span>
        <strong>{{ rewards.length }}</strong>
      </div>
      <div>
        <span>제재 사진 증빙</span>
        <strong>{{ sanctionPhotoCount }}</strong>
      </div>
    </section>

    <section class="evidence-section">
      <div class="section-head">
        <div>
          <h2>담당 검토 대기</h2>
          <p class="section-sub">소장이 최종 제출했고 본사 담당 검토·승인이 필요한 현장입니다.</p>
        </div>
        <span>{{ hqApprovalRows.length }}건</span>
      </div>
      <div class="table-scroll">
        <table class="data-table evidence-table">
          <thead>
            <tr>
              <th>현장</th>
              <th>평가 완료</th>
              <th>제출 시간</th>
              <th>처리</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading && !hqApprovalRows.length">
              <td colspan="4" class="empty-cell">담당 검토 대기 목록을 불러오는 중입니다.</td>
            </tr>
            <tr v-else-if="!hqApprovalRows.length">
              <td colspan="4" class="empty-cell">담당 검토 대기 현장이 없습니다.</td>
            </tr>
            <template v-for="row in hqApprovalRows" :key="`approval-group-${row.site_code}`">
              <tr>
                <td>
                  <strong>{{ approvalSiteLabel(row) }}</strong>
                  <span class="muted">({{ row.site_code }})</span>
                </td>
                <td>{{ row.site_complete_workers ?? 0 }} / {{ row.site_total_workers ?? 0 }}</td>
                <td>{{ row.site_submitted_at_label || formatDateTimeKst(row.site_submitted_at, "-") }}</td>
                <td class="actions-inline">
                  <button class="stitch-btn-primary" type="button" @click="toggleSiteEvidence(row)">
                    {{ selectedSiteCode === row.site_code ? "접기" : "증빙 확인" }}
                  </button>
                </td>
              </tr>
              <tr v-if="selectedSiteCode === row.site_code">
                <td colspan="4" class="site-evidence-cell">
                  <div class="site-evidence-head">
                    <strong>{{ approvalSiteLabel(row) }} 증빙 확인</strong>
                    <span class="muted">포상 사진과 제재 사진이 있는 근로자만 버튼이 표시됩니다.</span>
                  </div>
                  <div v-if="loadingSiteEvidence" class="empty-cell">현장 증빙을 불러오는 중입니다.</div>
                  <div v-else class="table-scroll">
                    <table class="data-table site-evidence-table">
                      <thead>
                        <tr>
                          <th>근로자</th>
                          <th>평가 상태</th>
                          <th>안전·제재</th>
                          <th>포상 사진</th>
                          <th>제재 사진</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-if="!siteEvidenceRows.length">
                          <td colspan="5" class="empty-cell">이 현장에서 확인할 근로자 증빙이 없습니다.</td>
                        </tr>
                        <tr v-for="worker in siteEvidenceRows" :key="worker.worker_id">
                          <td>{{ worker.name }}</td>
                          <td>{{ worker.eval_status_label || "-" }}</td>
                          <td>{{ worker.sanction_status_label || worker.safety_grade || "-" }}</td>
                          <td>
                            <button
                              v-if="worker.customer_reward?.photo_url || worker.customer_reward?.id"
                              class="link-btn"
                              type="button"
                              @click="openRewardPhoto(worker.customer_reward.id)"
                            >
                              포상 사진 확인
                            </button>
                            <span v-else class="muted">없음</span>
                          </td>
                          <td>
                            <button
                              v-if="worker.latest_sanction?.evidence_photo_url || worker.latest_sanction?.id"
                              class="link-btn"
                              type="button"
                              @click="openSanctionPhoto(worker.latest_sanction.id)"
                            >
                              제재 사진 확인
                            </button>
                            <span v-else class="muted">없음</span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <section class="evidence-section">
      <div class="section-head">
        <h2>포상 사진 증빙</h2>
        <span>{{ rewards.length }}건</span>
      </div>
      <div class="table-scroll">
        <table class="data-table evidence-table">
          <thead>
            <tr>
              <th>현장</th>
              <th>근로자</th>
              <th>가점</th>
              <th>제출 시간</th>
              <th>사진</th>
              <th>처리</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading && !rewards.length">
              <td colspan="6" class="empty-cell">포상 사진 증빙 목록을 불러오는 중입니다.</td>
            </tr>
            <tr v-else-if="!rewards.length">
              <td colspan="6" class="empty-cell">포상 사진 증빙 건이 없습니다.</td>
            </tr>
            <tr v-for="row in rewards" :key="`reward-${row.id}`">
              <td>{{ row.site_code }}</td>
              <td>{{ row.worker_name }}</td>
              <td>+{{ row.bonus_points }}</td>
              <td>{{ row.created_at_label || formatDateTimeKst(row.created_at, "-") }}</td>
              <td><button class="link-btn" type="button" @click="openRewardPhoto(row.id)">사진 확인</button></td>
              <td class="actions-inline">
                <button class="stitch-btn-primary" type="button" :disabled="reviewing" @click="approveReward(row.id)">승인</button>
                <button class="stitch-btn-secondary" type="button" :disabled="reviewing" @click="rejectReward(row.id)">반려</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="evidence-section">
      <div class="section-head">
        <h2>제재 사진 증빙</h2>
        <span>{{ sanctionPhotoCount }}건</span>
      </div>
      <div class="table-scroll">
        <table class="data-table evidence-table">
          <thead>
            <tr>
              <th>현장</th>
              <th>근로자</th>
              <th>제재 항목</th>
              <th>증빙 유형</th>
              <th>제출 시간</th>
              <th>사진</th>
              <th>처리</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading && !sanctions.length">
              <td colspan="7" class="empty-cell">제재 사진 증빙 목록을 불러오는 중입니다.</td>
            </tr>
            <tr v-else-if="!sanctions.length">
              <td colspan="7" class="empty-cell">제재 사진 증빙 건이 없습니다.</td>
            </tr>
            <tr v-for="row in sanctions" :key="`sanction-${row.id}`">
              <td>{{ row.site_code }}</td>
              <td>{{ row.worker_name }}</td>
              <td>{{ row.sanction_display_label || row.violation_label || row.violation_code }}</td>
              <td>{{ row.evidence_type_label || evidenceTypeLabel(row.evidence_type) }}</td>
              <td>{{ row.created_at_label || formatDateTimeKst(row.created_at, "-") }}</td>
              <td>
                <button v-if="row.evidence_photo_url" class="link-btn" type="button" @click="openSanctionPhoto(row.id)">
                  사진 확인
                </button>
                <span v-else class="muted">사진 없음</span>
              </td>
              <td class="actions-inline">
                <button class="stitch-btn-primary" type="button" :disabled="reviewing" @click="approveSanction(row.id)">승인</button>
                <button class="stitch-btn-secondary" type="button" :disabled="reviewing" @click="rejectSanction(row.id)">반려</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";
import { formatDateTimeKst } from "@/utils/datetime";

interface PendingReward {
  id: number;
  worker_name: string;
  site_code: string;
  bonus_points: number;
  created_at?: string | null;
  created_at_label?: string | null;
}

interface PendingSanction {
  id: number;
  worker_name: string;
  site_code: string;
  violation_code?: string;
  violation_label?: string;
  sanction_display_label?: string;
  evidence_type?: string | null;
  evidence_type_label?: string | null;
  evidence_photo_url?: string | null;
  created_at?: string | null;
  created_at_label?: string | null;
}

interface HqApprovalRow {
  site_code: string;
  site_name?: string | null;
  site_submitted_at?: string | null;
  site_submitted_at_label?: string | null;
  site_complete_workers?: number | null;
  site_total_workers?: number | null;
}

interface SiteEvidenceRow {
  worker_id: number;
  name: string;
  eval_status_label?: string | null;
  safety_grade?: string | null;
  sanction_status_label?: string | null;
  customer_reward?: { id: number; photo_url?: string | null } | null;
  latest_sanction?: { id: number; evidence_photo_url?: string | null } | null;
}

const loading = ref(false);
const reviewing = ref(false);
const loadError = ref("");
const rewards = ref<PendingReward[]>([]);
const sanctions = ref<PendingSanction[]>([]);
const hqApprovalRows = ref<HqApprovalRow[]>([]);
const selectedSiteCode = ref("");
const loadingSiteEvidence = ref(false);
const siteEvidenceRows = ref<SiteEvidenceRow[]>([]);

const totalPendingCount = computed(() => hqApprovalRows.value.length + rewards.value.length + sanctions.value.length);
const sanctionPhotoCount = computed(() => sanctions.value.filter((row) => !!row.evidence_photo_url).length);

function evidenceTypeLabel(type?: string | null) {
  return String(type || "").toUpperCase() === "PHOTO" ? "사진" : "코멘트";
}

function approvalSiteLabel(row: HqApprovalRow) {
  return row.site_name || row.site_code;
}

function openBlobInNewTab(blob: Blob) {
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener,noreferrer");
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

async function toggleSiteEvidence(row: HqApprovalRow) {
  if (selectedSiteCode.value === row.site_code) {
    selectedSiteCode.value = "";
    siteEvidenceRows.value = [];
    return;
  }
  selectedSiteCode.value = row.site_code;
  loadingSiteEvidence.value = true;
  siteEvidenceRows.value = [];
  try {
    const res = await api.get(`/functional-eval/hq/sites/${encodeURIComponent(row.site_code)}/evaluations`);
    siteEvidenceRows.value = Array.isArray(res.data?.eval_rows) ? res.data.eval_rows : [];
  } catch {
    window.alert("현장 증빙 목록을 불러오지 못했습니다.");
  } finally {
    loadingSiteEvidence.value = false;
  }
}

async function openRewardPhoto(rewardId: number) {
  try {
    const res = await api.get(`/functional-eval/customer-rewards/${rewardId}/photo`, { responseType: "blob" });
    openBlobInNewTab(res.data);
  } catch {
    window.alert("포상 사진을 확인할 수 없습니다.");
  }
}

async function openSanctionPhoto(sanctionId: number) {
  try {
    const res = await api.get(`/functional-eval/sanctions/${sanctionId}/evidence-photo`, { responseType: "blob" });
    openBlobInNewTab(res.data);
  } catch {
    window.alert("제재 증빙 사진을 확인할 수 없습니다.");
  }
}

async function loadQueues() {
  loading.value = true;
  loadError.value = "";
  try {
    const [approvalRes, rewardRes, sanctionRes] = await Promise.all([
      api.get("/functional-eval/hq/approvals/pending"),
      api.get("/functional-eval/hq/customer-rewards/pending"),
      api.get("/functional-eval/hq/sanctions/pending"),
    ]);
    const roleItems = Array.isArray(approvalRes.data?.items) ? approvalRes.data.items : [];
    const officerItems = Array.isArray(approvalRes.data?.officer_items) ? approvalRes.data.officer_items : [];
    const directorItems = Array.isArray(approvalRes.data?.director_items) ? approvalRes.data.director_items : [];
    hqApprovalRows.value = roleItems.length || approvalRes.data?.hq_role !== "admin" ? roleItems : directorItems.length ? directorItems : officerItems;
    rewards.value = Array.isArray(rewardRes.data?.items) ? rewardRes.data.items : [];
    sanctions.value = Array.isArray(sanctionRes.data?.items) ? sanctionRes.data.items : [];
    window.dispatchEvent(new CustomEvent("besma-fe-review-updated"));
  } catch {
    loadError.value = "승인 대기 목록을 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
}

async function approveReward(rewardId: number) {
  reviewing.value = true;
  try {
    await api.post(`/functional-eval/hq/customer-rewards/${rewardId}/approve`, {});
    await loadQueues();
  } catch {
    window.alert("포상 승인에 실패했습니다.");
  } finally {
    reviewing.value = false;
  }
}

async function rejectReward(rewardId: number) {
  const rejectNote = window.prompt("반려 사유를 입력하세요.") || "";
  reviewing.value = true;
  try {
    await api.post(`/functional-eval/hq/customer-rewards/${rewardId}/reject`, { reject_note: rejectNote });
    await loadQueues();
  } catch {
    window.alert("포상 반려에 실패했습니다.");
  } finally {
    reviewing.value = false;
  }
}

async function approveSanction(sanctionId: number) {
  reviewing.value = true;
  try {
    await api.post(`/functional-eval/hq/sanctions/${sanctionId}/approve`, {});
    await loadQueues();
  } catch {
    window.alert("제재 승인에 실패했습니다.");
  } finally {
    reviewing.value = false;
  }
}

async function rejectSanction(sanctionId: number) {
  const rejectNote = window.prompt("반려 사유를 입력하세요.") || "";
  reviewing.value = true;
  try {
    await api.post(`/functional-eval/hq/sanctions/${sanctionId}/reject`, { reject_note: rejectNote });
    await loadQueues();
  } catch {
    window.alert("제재 반려에 실패했습니다.");
  } finally {
    reviewing.value = false;
  }
}

onMounted(loadQueues);
</script>

<style scoped>
.fe-evidence-page {
  display: grid;
  gap: 16px;
  position: relative;
}

.fe-evidence-page.is-loading {
  min-height: 420px;
}

.loading-overlay {
  position: fixed;
  inset: 52px 0 0 240px;
  z-index: 300;
  display: grid;
  place-items: start center;
  padding-top: 120px;
  background: rgba(241, 245, 249, 0.68);
  backdrop-filter: blur(2px);
  pointer-events: none;
}

.loading-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  min-width: min(360px, calc(100vw - 48px));
  padding: 22px 24px;
  border-radius: 16px;
  border: 1px solid #dbeafe;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.14);
  color: #0f172a;
}

.loading-card small,
.section-sub,
.muted {
  color: #64748b;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: 3px solid #bfdbfe;
  border-top-color: #2563eb;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.page-head,
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page-title,
.section-head h2 {
  margin: 0;
}

.page-title {
  font-size: 22px;
}

.page-sub,
.section-sub {
  margin: 6px 0 0;
}

.evidence-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.evidence-summary > div,
.evidence-section {
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 8px;
}

.evidence-summary > div {
  padding: 14px;
}

.evidence-summary .summary-card--primary {
  border-color: #2563eb;
  background: #eff6ff;
}

.evidence-summary span {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.evidence-summary strong {
  display: block;
  margin-top: 6px;
  font-size: 24px;
  color: #0f172a;
}

.evidence-section {
  padding: 16px;
}

.section-head {
  margin-bottom: 12px;
}

.section-head span {
  color: #2563eb;
  font-weight: 700;
}

.table-scroll {
  overflow-x: auto;
}

.evidence-table {
  min-width: 900px;
}

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 24px;
}

.site-evidence-cell {
  background: #f8fafc;
  padding: 14px;
}

.site-evidence-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.site-evidence-table {
  min-width: 760px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.actions-inline {
  display: flex;
  gap: 6px;
  align-items: center;
  white-space: nowrap;
}

.load-error {
  margin: 0;
  color: #dc2626;
}

@media (max-width: 760px) {
  .evidence-summary {
    grid-template-columns: 1fr;
  }

  .loading-overlay {
    inset: 44px 0 0;
    padding: 96px 16px 0;
  }
}
</style>
