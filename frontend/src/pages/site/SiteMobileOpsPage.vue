<template>
  <div class="mobile-shell">
    <div class="mobile-card">
      <div class="page-header">
        <h1>{{ pageTitle }}</h1>
        <div class="header-actions">
          <button class="btn-secondary" @click="goSiteSearch">현장 검색</button>
          <button class="btn-secondary" @click="goCommunications">소통자료</button>
          <button class="btn-secondary" @click="startNewScenario">새 작업 시작</button>
        </div>
      </div>

      <!-- Site context (test mode) -->
      <section class="ops-card" v-if="auth.isTestPersonaMode && !auth.user?.site_id">
        <div><strong>테스트 site context</strong></div>
        <div class="helper">현재 계정은 site_id가 없어 테스트용 site context가 필요합니다.</div>
        <div class="field-row">
          <select v-model.number="selectedSiteContextId" @change="onChangeSiteContext">
            <option :value="0">현장 선택</option>
            <option v-for="s in siteOptions" :key="s.id" :value="s.id">
              {{ s.site_name }} (#{{ s.id }})
            </option>
          </select>
          <button class="btn-secondary" :disabled="siteOptionsLoading" @click="loadSiteOptions">
            새로고침
          </button>
        </div>
      </section>

      <p v-if="!effectiveSiteId" class="msg hint">현장을 선택하세요.</p>
      <template v-else>
        <section class="ops-card">
          <h2>오늘 현장 인원/서명 현황</h2>
          <div class="status-grid">
            <div><strong>오늘 출역 인원</strong><div>{{ workforceSummary.totalWorkers }}명</div></div>
            <div><strong>서명 완료 인원</strong><div>{{ workforceSummary.signedWorkers }}명</div></div>
            <div><strong>미서명 인원</strong><div>{{ workforceSummary.unsignedWorkers }}명</div></div>
          </div>
          <table class="basic-table" v-if="siteWorkers.length > 0">
            <thead>
              <tr>
                <th>이름</th>
                <th>부서</th>
                <th>직책</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="w in siteWorkers" :key="w.person_id">
                <td>{{ w.name }}</td>
                <td>{{ w.department_name || "-" }}</td>
                <td>{{ w.position_name || "-" }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <SitePlanCreateCard
          :key="`plan-create-${scenarioEpoch}`"
          :site-id="effectiveSiteId"
          :current-plan="currentPlan"
          @plan-created="onPlanCreated"
          @reset-plan="resetPlan"
        />

        <SitePlanItemsEditor
          :key="`plan-items-${scenarioEpoch}-${currentPlan?.id ?? 'none'}`"
          :plan-id="currentPlan?.id ?? null"
          :items="planItems"
          @item-added="onItemAdded"
          @risks-adopted="onRisksAdopted"
          @no-risk-confirmed="onNoRiskConfirmed"
          @refresh-plan="refreshPlan"
        />

        <SiteDistributionCreateCard
          :key="`dist-create-${scenarioEpoch}-${currentPlan?.id ?? 'none'}`"
          :plan-id="currentPlan?.id ?? null"
          :site-id="effectiveSiteId"
          :has-adopted-items="hasAdoptedItems"
          @distribution-created="onDistributionCreated"
        />

        <SiteTbmOpsPanel
          :distribution-id="currentDistributionId"
          :distribution="currentDistribution"
          :recent-distributions="recentDistributions"
          :site-id="effectiveSiteId"
          @select-distribution="onSelectDistribution"
          @refresh-distribution="refreshDistribution"
          @tbm-started="refreshDistribution"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

import SitePlanCreateCard from "@/components/site/SitePlanCreateCard.vue";
import SitePlanItemsEditor from "@/components/site/SitePlanItemsEditor.vue";
import SiteDistributionCreateCard from "@/components/site/SiteDistributionCreateCard.vue";
import SiteTbmOpsPanel from "@/components/site/SiteTbmOpsPanel.vue";

interface PlanItem {
  id: number;
  work_name: string;
  work_description: string;
  team_label: string | null;
  risk_refs: any[];
}

interface Plan {
  id: number;
  work_date: string;
  status: string;
  items: PlanItem[];
}

interface DistSummary {
  id: number;
  target_date: string;
  is_tbm_active: boolean;
  worker_count: number;
}

interface SiteOption {
  id: number;
  site_name: string;
}

interface SiteWorker {
  person_id: number;
  name: string;
  department_name: string | null;
  position_name: string | null;
}

const auth = useAuthStore();
const router = useRouter();
const pageTitle = computed(() => {
  const name = auth.user?.name?.trim();
  return name ? `${name} 님 작업 화면` : "현장 작업 화면";
});

const siteOptions = ref<SiteOption[]>([]);
const selectedSiteContextId = ref<number>(auth.effectiveSiteId ?? 0);
const siteOptionsLoading = ref(false);
const scenarioEpoch = ref(0);

const currentPlan = ref<Plan | null>(null);
const planItems = computed<PlanItem[]>(() => currentPlan.value?.items ?? []);
const noRiskConfirmedByItem = ref<Record<number, boolean>>({});
const hasAdoptedItems = computed(() =>
  planItems.value.some((item) =>
    item.risk_refs?.some((r: any) => r.link_type === "ADOPTED" || r.is_selected === true),
  ) || Object.values(noRiskConfirmedByItem.value).some((flag) => flag),
);

const currentDistributionId = ref<number | null>(null);
const currentDistribution = ref<any>(null);
const recentDistributions = ref<DistSummary[]>([]);
const siteWorkers = ref<SiteWorker[]>([]);

const effectiveSiteId = computed<number>(
  () => auth.user?.site_id ?? selectedSiteContextId.value ?? 0,
);
const workforceSummary = computed(() => {
  const signedPersonIds = new Set(
    (currentDistribution.value?.workers ?? [])
      .filter((w: any) => !!w.start_signed_at)
      .map((w: any) => w.person_id),
  );
  const totalWorkers = siteWorkers.value.length;
  const signedWorkers = signedPersonIds.size;
  return {
    totalWorkers,
    signedWorkers,
    unsignedWorkers: Math.max(0, totalWorkers - signedWorkers),
  };
});

async function loadSiteOptions() {
  siteOptionsLoading.value = true;
  try {
    const res = await api.get("/sites");
    siteOptions.value = res.data;
  } catch {
    siteOptions.value = [];
  } finally {
    siteOptionsLoading.value = false;
  }
}

function onChangeSiteContext() {
  if (selectedSiteContextId.value > 0) {
    auth.setTestSiteContext(selectedSiteContextId.value);
    startNewScenario();
    loadRecentDistributions();
  }
}

function onPlanCreated(plan: Plan) {
  currentPlan.value = plan;
  currentDistributionId.value = null;
  currentDistribution.value = null;
  noRiskConfirmedByItem.value = {};
}

function resetPlan() {
  currentPlan.value = null;
  currentDistributionId.value = null;
  currentDistribution.value = null;
  noRiskConfirmedByItem.value = {};
}

function startNewScenario() {
  resetPlan();
  scenarioEpoch.value += 1;
}

function goCommunications() {
  router.push({ name: "site-mobile-communications" });
}

function goSiteSearch() {
  router.push({ name: "site-mobile-site-search" });
}

async function refreshPlan() {
  if (!currentPlan.value) return;
  try {
    const res = await api.get(`/daily-work-plans/${currentPlan.value.id}`);
    currentPlan.value = res.data;
  } catch {
    /* keep current state */
  }
}

function onItemAdded(_item: PlanItem) {
  void refreshPlan();
}

function onRisksAdopted(_itemId: number) {
  void refreshPlan();
}

function onNoRiskConfirmed(payload: { itemId: number; confirmed: boolean }) {
  noRiskConfirmedByItem.value[payload.itemId] = payload.confirmed;
}

function onDistributionCreated(dist: any) {
  currentDistributionId.value = dist.id;
  currentDistribution.value = null;
  void loadRecentDistributions();
  void refreshDistribution();
}

async function onSelectDistribution(id: number) {
  currentDistributionId.value = id;
  await refreshDistribution();
}

async function refreshDistribution() {
  if (!currentDistributionId.value) return;
  try {
    const res = await api.get(
      `/daily-work-plans/distributions/${currentDistributionId.value}`,
    );
    currentDistribution.value = res.data;
    void loadSiteWorkers();
  } catch {
    currentDistribution.value = null;
  }
}

async function loadSiteWorkers() {
  const siteId = effectiveSiteId.value;
  if (!siteId) return;
  try {
    const targetDate = currentPlan.value?.work_date || new Date().toISOString().slice(0, 10);
    const res = await api.get(`/sites/${siteId}/workers`, {
      params: { target_date: targetDate },
    });
    siteWorkers.value = res.data ?? [];
  } catch {
    siteWorkers.value = [];
  }
}

async function loadRecentDistributions() {
  const siteId = effectiveSiteId.value;
  if (!siteId) return;
  try {
    const res = await api.get("/daily-work-plans/distributions", {
      params: { site_id: siteId, limit: 10 },
    });
    recentDistributions.value = res.data ?? [];
  } catch {
    recentDistributions.value = [];
  }
}

onMounted(async () => {
  if (auth.isTestPersonaMode && !auth.user?.site_id) {
    await loadSiteOptions();
  }
  if (effectiveSiteId.value) {
    loadRecentDistributions();
    loadSiteWorkers();
  }
});
</script>

<style scoped>
.mobile-shell {
  min-height: 100%;
  background: #f3f4f6;
  padding: 8px;
}

.mobile-card {
  max-width: 760px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.header-actions {
  display: flex;
  gap: 6px;
}

h1 {
  font-size: 20px;
  margin: 0 0 12px;
  color: #1e293b;
}

.helper {
  color: #6b7280;
  font-size: 13px;
  margin-bottom: 8px;
}

/* Shared card style */
:deep(.ops-card) {
  background: #fff;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 10px;
}

:deep(.ops-card h2) {
  font-size: 16px;
  margin: 0 0 10px;
  color: #334155;
}

/* Fields */
:deep(.field-row) {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

:deep(.field-row label) {
  min-width: 64px;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

:deep(.field-row input),
:deep(.field-row select) {
  flex: 1;
  min-height: 40px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 0 10px;
  font-size: 14px;
}

/* Buttons */
:deep(.btn-primary) {
  width: 100%;
  min-height: 44px;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

:deep(.btn-primary:disabled) {
  opacity: 0.5;
  cursor: not-allowed;
}

:deep(.btn-secondary) {
  min-height: 38px;
  background: #e5e7eb;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  padding: 0 12px;
}

:deep(.btn-secondary.active) {
  background: #bfdbfe;
  font-weight: 600;
}

:deep(.btn-small) {
  min-height: 32px;
  padding: 0 10px;
  background: #e5e7eb;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}

:deep(.btn-small.adopt) {
  background: #bbf7d0;
  color: #166534;
}

:deep(.btn-text) {
  background: none;
  border: none;
  color: #2563eb;
  font-size: 13px;
  cursor: pointer;
  text-decoration: underline;
}

/* Messages */
:deep(.msg) {
  margin-top: 8px;
  font-size: 13px;
  font-weight: 600;
}

:deep(.msg.error) {
  color: #dc2626;
}

:deep(.msg.success) {
  color: #16a34a;
}

:deep(.msg.hint) {
  color: #9ca3af;
  font-weight: 400;
}

/* Plan badge */
:deep(.plan-badge) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 14px;
}

/* Item cards */
:deep(.add-form) {
  border: 1px dashed #d1d5db;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 10px;
}

:deep(.item-card) {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 8px;
}

:deep(.item-header) {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

:deep(.badge) {
  background: #bbf7d0;
  color: #166534;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
}

:deep(.item-desc) {
  font-size: 13px;
  color: #6b7280;
}

:deep(.item-team) {
  font-size: 12px;
  color: #9ca3af;
}

:deep(.item-actions) {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

/* Recommendation list */
:deep(.rec-list) {
  margin-top: 8px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

:deep(.rec-header) {
  background: #f9fafb;
  padding: 6px 10px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid #e5e7eb;
}

:deep(.rec-row) {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid #f3f4f6;
  cursor: pointer;
  font-size: 13px;
}

:deep(.rec-row:last-child) {
  border-bottom: none;
}

:deep(.rec-detail) {
  flex: 1;
}

:deep(.rec-meta) {
  font-size: 11px;
  color: #9ca3af;
}

/* Worker selection */
:deep(.worker-section) {
  margin: 10px 0;
}

:deep(.worker-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

:deep(.worker-select) {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  max-height: 240px;
  overflow-y: auto;
}

:deep(.worker-row) {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid #f3f4f6;
  font-size: 14px;
  cursor: pointer;
}

:deep(.worker-row:last-child) {
  border-bottom: none;
}

:deep(.worker-row.select-all) {
  background: #f9fafb;
  font-weight: 600;
}

:deep(.worker-meta) {
  font-size: 12px;
  color: #9ca3af;
  margin-left: auto;
}

/* Status grid */
:deep(.status-grid) {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 8px;
  font-size: 14px;
}

:deep(.action-row) {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  margin-bottom: 8px;
}

/* Recent distributions */
:deep(.recent-box) {
  margin-bottom: 10px;
}

:deep(.recent-grid) {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
  margin-top: 6px;
}

/* Worker status list */
:deep(.worker-list) {
  margin-top: 10px;
}

:deep(.worker-list-header) {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
}

:deep(.worker-status-row) {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px 10px;
  margin-bottom: 6px;
}

:deep(.worker-name) {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

:deep(.ack-badge) {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}

:deep(.ack-badge.distributed) {
  background: #fef3c7;
  color: #92400e;
}

:deep(.ack-badge.start_signed) {
  background: #bbf7d0;
  color: #166534;
}

:deep(.ack-badge.end_signed) {
  background: #bfdbfe;
  color: #1e40af;
}

:deep(.worker-times) {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #6b7280;
}

:deep(.issue-flag) {
  color: #dc2626;
  font-weight: 600;
}

:deep(.worker-link-actions) {
  margin-top: 4px;
}

/* Paste import styles */
:deep(.tab-bar) {
  display: flex;
  gap: 0;
  margin-bottom: 10px;
  border-bottom: 2px solid #e5e7eb;
}

:deep(.tab-btn) {
  flex: 1;
  padding: 8px 0;
  background: none;
  border: none;
  font-size: 14px;
  font-weight: 600;
  color: #9ca3af;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
}

:deep(.tab-btn.active) {
  color: #2563eb;
  border-bottom-color: #2563eb;
}

:deep(.paste-area) {
  width: 100%;
  min-height: 160px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px;
  font-size: 13px;
  font-family: inherit;
  resize: vertical;
  margin-bottom: 8px;
  box-sizing: border-box;
}

:deep(.parsed-summary) {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 10px;
  font-size: 13px;
  display: grid;
  gap: 2px;
}

:deep(.items-preview) {
  margin-bottom: 8px;
}

:deep(.preview-item) {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 6px 8px;
  margin-bottom: 4px;
}

:deep(.preview-item-header) {
  display: flex;
  align-items: center;
  gap: 6px;
}

:deep(.preview-idx) {
  background: #e5e7eb;
  border-radius: 4px;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

:deep(.preview-input) {
  flex: 1;
  min-height: 32px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 0 8px;
  font-size: 13px;
}

:deep(.btn-icon) {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  color: #9ca3af;
  padding: 4px;
}

:deep(.btn-icon:hover) {
  color: #dc2626;
}

:deep(.preview-workers) {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
  padding-left: 28px;
}

:deep(.add-item-row) {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}

:deep(.preview-actions) {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 8px;
}

:deep(.done-msg) {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #1e40af;
  text-align: center;
  margin-bottom: 8px;
}

@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
  }
  :deep(.action-row) {
    grid-template-columns: 1fr;
  }
  :deep(.status-grid) {
    grid-template-columns: 1fr;
  }
  :deep(.field-row) {
    flex-direction: column;
    align-items: stretch;
  }
  :deep(.field-row label) {
    min-width: unset;
  }
  :deep(.worker-times) {
    flex-direction: column;
    gap: 2px;
  }
  :deep(.preview-actions) {
    grid-template-columns: 1fr;
  }
}
</style>
