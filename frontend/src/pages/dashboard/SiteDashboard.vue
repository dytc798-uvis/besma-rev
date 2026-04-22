<template>
  <div class="site-dash-page">
    <div class="site-dash-grid">
      <BaseCard title="SITE 대시보드">
        <template #actions>
          <button type="button" class="stitch-btn-secondary" @click="load">새로고침</button>
        </template>
        <template v-if="riskDbOverview">
          <section class="site-dash-alerts" aria-labelledby="site-dash-alerts-title">
            <h3 id="site-dash-alerts-title" class="site-dash-alerts-title">처리 필요 알림</h3>
            <p class="site-dash-alerts-sub">관리대장 화면에서 처리합니다. 문서취합 알림과 별도입니다.</p>
            <p class="site-ledger-kpi-intro site-ledger-kpi-intro--tight">운영 접수·조치와 DB 등록 요청 상태</p>
            <h4 class="site-ledger-section-title">근로자의견청취</h4>
            <section class="site-ledger-kpi-grid">
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('unreceived', 'voice')">
                <span class="site-ledger-kpi-label">접수 대기</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.worker_voice.unreceived }}</span>
                <span class="site-ledger-kpi-hint">현장 검토 필요</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('in_progress', 'voice')">
                <span class="site-ledger-kpi-label">조치중</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.worker_voice.in_progress }}</span>
                <span class="site-ledger-kpi-hint">조치 진행 중</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('action_completed', 'voice')">
                <span class="site-ledger-kpi-label">조치 완료</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.worker_voice.action_completed }}</span>
                <span class="site-ledger-kpi-hint">운영 조치 완료</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('db_needed', 'voice')">
                <span class="site-ledger-kpi-label">DB 등록 요청 필요</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.worker_voice.db_request_needed }}</span>
                <span class="site-ledger-kpi-hint">관리대장에서 요청</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('db_requested', 'voice')">
                <span class="site-ledger-kpi-label">DB 등록 요청 완료</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.worker_voice.db_requested }}</span>
                <span class="site-ledger-kpi-hint">본사 승인 대기</span>
              </button>
            </section>
            <div class="site-ledger-divider" aria-hidden="true" />
            <h4 class="site-ledger-section-title">부적합사항</h4>
            <section class="site-ledger-kpi-grid">
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('unreceived', 'nonconf')">
                <span class="site-ledger-kpi-label">접수 대기</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.nonconformity.unreceived }}</span>
                <span class="site-ledger-kpi-hint">현장 검토 필요</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('in_progress', 'nonconf')">
                <span class="site-ledger-kpi-label">조치중</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.nonconformity.in_progress }}</span>
                <span class="site-ledger-kpi-hint">조치 진행 중</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('action_completed', 'nonconf')">
                <span class="site-ledger-kpi-label">조치 완료</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.nonconformity.action_completed }}</span>
                <span class="site-ledger-kpi-hint">운영 조치 완료</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('db_needed', 'nonconf')">
                <span class="site-ledger-kpi-label">DB 등록 요청 필요</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.nonconformity.db_request_needed }}</span>
                <span class="site-ledger-kpi-hint">관리대장에서 요청</span>
              </button>
              <button type="button" class="site-ledger-kpi" @click="goSiteLedgerFilter('db_requested', 'nonconf')">
                <span class="site-ledger-kpi-label">DB 등록 요청 완료</span>
                <span class="site-ledger-kpi-value">{{ riskDbOverview.site.nonconformity.db_requested }}</span>
                <span class="site-ledger-kpi-hint">본사 승인 대기</span>
              </button>
            </section>
          </section>
        </template>

        <div class="site-dash-doc-block">
          <p class="mb-3 text-sm font-semibold text-slate-700">문서·제안 현황</p>
          <p class="mb-4 text-sm text-slate-500">문서취합(내 현장 문서)과 운영 아이디어 제안 요약</p>
          <section class="site-kpi-grid">
            <KpiCard label="전체 문서 수" :value="data?.total_documents ?? '—'" accent="blue" />
            <KpiCard label="제출/검토 중" :value="data?.pending_documents ?? '—'" accent="orange" />
            <KpiCard label="반려 문서" :value="data?.rejected_documents ?? '—'" accent="red" />
            <KpiCard label="현장 의견 접수" :value="data?.total_opinions ?? '—'" accent="slate" />
            <KpiCard label="미조치 의견" :value="data?.pending_opinions ?? '—'" accent="slate" />
          </section>
          <div class="site-opinion-cta-row">
            <button type="button" class="stitch-btn-secondary" @click="goOpinions">
              운영 아이디어 제안/결과 확인
            </button>
          </div>
        </div>
      </BaseCard>

      <BaseCard title="본사-현장 소통" class="site-comm-card">
        <template #actions>
          <span class="weather-updated">미확인 {{ unreadCommunicationCount }}건</span>
        </template>
        <p class="weather-snapshot-meta">본사에서 남긴 코멘트/승인·반려 의견만 표시됩니다.</p>
        <div class="comm-table-wrap">
          <table class="comm-table">
            <thead>
              <tr>
                <th>날짜</th>
                <th>문서</th>
                <th>코멘트</th>
                <th>확인</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in displayedCommunicationItems"
                :key="row.item_key"
                :class="{ 'comm-row-unread': !isCommunicationRead(row.item_key) }"
              >
                <td>{{ formatDateTimeKst(row.created_at, "—") }}</td>
                <td>{{ row.title }}</td>
                <td class="comm-comment-cell">{{ row.comment_text }}</td>
                <td>
                  <button
                    type="button"
                    class="stitch-btn-secondary"
                    :disabled="isCommunicationRead(row.item_key)"
                    @click="confirmAndOpenDetail(row)"
                  >
                    {{ isCommunicationRead(row.item_key) ? "확인됨" : "확인" }}
                  </button>
                </td>
              </tr>
              <tr v-if="displayedCommunicationItems.length === 0">
                <td colspan="4" class="neutral">표시할 본사-현장 소통이 없습니다.</td>
              </tr>
            </tbody>
          </table>
          <div class="site-opinion-cta-row">
            <button type="button" class="stitch-btn-secondary" @click="showUnreadOnly = !showUnreadOnly">
              {{ showUnreadOnly ? "전체 보기" : "미확인만 보기" }}
            </button>
          </div>
        </div>
      </BaseCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
import { fetchRiskDbOverviewOptional, type RiskDbOverviewPayload } from "@/services/riskDbOverview";
import { BaseCard, KpiCard } from "@/components/product";
import { formatDateTimeKst } from "@/utils/datetime";
import type { LedgerDashboardFilter } from "@/utils/ledgerDashboardFilter";
import { getReadSiteCommunicationKeys, markSiteCommunicationRead } from "@/utils/siteCommunicationRead";
import { useAuthStore } from "@/stores/auth";

interface DashboardSummary {
  total_documents: number;
  pending_documents: number;
  rejected_documents: number;
  total_opinions: number;
  pending_opinions: number;
}

interface SiteCommunicationItem {
  item_key: string;
  source: string;
  source_id: number;
  document_id: number;
  title: string;
  site_id: number;
  site_name: string;
  user_name: string;
  user_role: string;
  comment_text: string;
  created_at: string | null;
}

const router = useRouter();
const auth = useAuthStore();
const data = ref<DashboardSummary | null>(null);
const communicationItems = ref<SiteCommunicationItem[]>([]);
const riskDbOverview = ref<RiskDbOverviewPayload | null>(null);
const summaryError = ref(false);
const showUnreadOnly = ref(true);
const communicationReadKeys = ref<Set<string>>(new Set());
const unreadCommunicationCount = ref(0);

function goSiteLedgerFilter(filter: LedgerDashboardFilter, board: "voice" | "nonconf") {
  const name = board === "voice" ? "site-worker-voice" : "site-nonconformities";
  router.push({ name, query: { filter } });
}

function goOpinions() {
  router.push({ name: "site-opinions" });
}

function isCommunicationRead(itemKey: string) {
  return communicationReadKeys.value.has(itemKey);
}

const displayedCommunicationItems = computed(() =>
  showUnreadOnly.value
    ? communicationItems.value.filter((row) => !isCommunicationRead(row.item_key))
    : communicationItems.value,
);

function syncReadState() {
  const loginId = auth.user?.login_id ?? null;
  communicationReadKeys.value = getReadSiteCommunicationKeys(loginId);
  unreadCommunicationCount.value = communicationItems.value.filter((row) => !communicationReadKeys.value.has(row.item_key)).length;
}

async function confirmAndOpenDetail(row: SiteCommunicationItem) {
  const loginId = auth.user?.login_id ?? null;
  markSiteCommunicationRead(loginId, row.item_key);
  syncReadState();
  await router.push({ name: "site-document-detail", params: { id: String(row.document_id) } });
}

async function loadSiteCommunications() {
  try {
    const res = await api.get("/documents/site-communications", { params: { limit: 120 } });
    communicationItems.value = (res.data?.items ?? []) as SiteCommunicationItem[];
  } catch {
    communicationItems.value = [];
  } finally {
    syncReadState();
  }
}

async function load() {
  summaryError.value = false;
  const summaryPromise = api.get<DashboardSummary>("/dashboard/summary").then(
    (res) => {
      data.value = res.data;
    },
    () => {
      summaryError.value = true;
      data.value = null;
    },
  );
  const riskPromise = fetchRiskDbOverviewOptional().then((data) => {
    riskDbOverview.value = data;
  });
  const communicationsPromise = loadSiteCommunications();
  await Promise.all([summaryPromise, riskPromise, communicationsPromise]);
}

onMounted(load);
</script>

<style scoped>
.site-dash-page {
  width: 100%;
}

.site-dash-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.9fr);
  gap: 16px;
  align-items: start;
}

.site-kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.site-dash-alerts {
  margin-bottom: 18px;
  padding-bottom: 4px;
  border-bottom: 1px solid #e2e8f0;
}

.site-dash-alerts-title {
  margin: 0 0 6px;
  font-size: 17px;
  font-weight: 800;
  color: #0f172a;
}

.site-dash-alerts-sub {
  margin: 0 0 10px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.45;
}

.site-dash-doc-block {
  margin-top: 8px;
}

.site-opinion-cta-row {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}

.site-ledger-kpi-intro {
  margin: 14px 0 8px;
  font-size: 12px;
  color: #64748b;
}

.site-ledger-kpi-intro--tight {
  margin-top: 0;
}

.site-ledger-section-title {
  margin: 12px 0 8px;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.site-ledger-kpi-intro + .site-ledger-section-title {
  margin-top: 4px;
}

.site-ledger-divider {
  height: 1px;
  margin: 14px 0 4px;
  background: linear-gradient(to right, transparent, #e2e8f0 8%, #e2e8f0 92%, transparent);
}

.site-ledger-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
}

.site-ledger-kpi {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
  cursor: pointer;
  text-align: left;
}

.site-ledger-kpi:hover {
  border-color: #cbd5e1;
  background: #fff;
}

.site-ledger-kpi-label {
  font-size: 11px;
  font-weight: 700;
  color: #475569;
}

.site-ledger-kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.site-ledger-kpi-hint {
  font-size: 11px;
  color: #64748b;
  line-height: 1.3;
}

.site-comm-card {
  min-height: 100%;
}

.weather-snapshot-meta {
  margin: 0 0 10px;
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
}

.weather-snapshot-sep {
  margin: 0 6px;
  color: #94a3b8;
}

.weather-updated {
  color: #64748b;
  font-size: 12px;
}

.comm-table-wrap {
  overflow: auto;
}

.comm-table {
  width: 100%;
  border-collapse: collapse;
}

.comm-table th,
.comm-table td {
  border-bottom: 1px solid #e2e8f0;
  padding: 8px 6px;
  font-size: 12px;
  text-align: left;
  vertical-align: top;
}

.comm-comment-cell {
  max-width: 360px;
  white-space: pre-wrap;
}

.comm-row-unread {
  background: #fff7ed;
}

.neutral {
  color: #64748b;
}

@media (max-width: 900px) {
  .site-dash-grid {
    grid-template-columns: 1fr;
  }

  .site-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .site-kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
