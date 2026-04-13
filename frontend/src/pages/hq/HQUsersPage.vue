<template>
  <div class="user-mgmt-page">
    <header class="page-head">
      <div>
        <h1 class="page-title">근로자 · 사용자 관리</h1>
        <p class="page-sub">계정·안전 기록 연동 (API)</p>
      </div>
    </header>

    <div class="user-mgmt-grid">
    <BaseCard class="user-list-panel !flex !flex-col !gap-3 !py-5 !px-[18px]">
      <template #head>
        <div class="flex w-full items-center justify-between gap-2">
          <h2 class="m-0 text-[15px] font-bold text-slate-900">사용자 목록</h2>
          <button type="button" class="stitch-btn-secondary" :disabled="loadingList" @click="loadUsers">새로고침</button>
        </div>
      </template>

      <FilterBar class="!mb-0">
        <input v-model="keyword" type="text" placeholder="이름/계정 검색" class="search-input w-full min-w-0 flex-1" />
      </FilterBar>

      <div v-if="loadingList" class="panel-state">사용자 목록 불러오는 중...</div>
      <div v-else-if="filteredUsers.length === 0" class="panel-state">표시할 사용자가 없습니다.</div>
      <WorkerTable
        v-else
        :users="filteredUsers"
        :selected-user-id="selectedUserId"
        :role-label="roleLabel"
        @select="selectUser"
      />
    </BaseCard>

    <BaseCard class="detail-panel !min-h-[420px] !p-[22px]" title="사용자 상세">

      <div v-if="!selectedUser" class="panel-state">선택된 사용자가 없습니다.</div>
      <div v-else-if="loadingDetail" class="panel-state">사용자 상세 불러오는 중...</div>
      <div v-else>
        <div class="detail-grid">
          <div class="detail-item"><span>이름</span><strong>{{ selectedUser.name }}</strong></div>
          <div class="detail-item"><span>역할</span><strong>{{ roleLabel(selectedUser.role) }}</strong></div>
          <div class="detail-item"><span>소속 현장</span><strong>{{ siteNameLabel }}</strong></div>
          <div class="detail-item"><span>직영/협력사/팀명</span><strong>{{ teamLabel }}</strong></div>
          <div class="detail-item"><span>기능인등급/안전점수</span><strong>{{ skillAndScoreLabel }}</strong></div>
          <div class="detail-item"><span>오늘 작업</span><strong>{{ todayWorkLabel }}</strong></div>
          <div class="detail-item"><span>출역 여부</span><strong>{{ attendanceLabel }}</strong></div>
          <div class="detail-item"><span>TBM 서명 여부</span><strong>{{ tbmSignLabel }}</strong></div>
        </div>

        <div v-if="selectedUser" class="user-pw-reset">
          <button type="button" class="stitch-btn-secondary" :disabled="resettingPw" @click="handleResetPassword">
            {{ resettingPw ? "처리 중..." : "비밀번호 초기화" }}
          </button>
          <p class="user-pw-reset-hint">
            임시 비밀번호가 생성됩니다. 저장·조회 API는 없으며, 발급 직후 한 번만 화면에 표시됩니다.
          </p>
        </div>

        <div class="stitch-kpi-grid kpi-user">
          <KpiCard
            label="최근 문서"
            :value="recentDocumentLabel"
            accent="blue"
            badge-text="문서"
            badge-tone="info"
            compact
          />
          <KpiCard
            label="최근 교육"
            value="연동 전"
            accent="slate"
            badge-text="교육"
            badge-tone="neutral"
            compact
          />
          <KpiCard
            label="최근 위반"
            value="연동 전"
            accent="orange"
            badge-text="위반"
            badge-tone="warn"
            compact
          />
          <KpiCard
            label="최근 피드백"
            :value="recentFeedbackLabel"
            accent="red"
            badge-text="피드백"
            badge-tone="danger"
            compact
          />
        </div>
      </div>
    </BaseCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";
import { BaseCard, FilterBar, KpiCard, WorkerTable } from "@/components/product";

interface UserRow {
  id: number;
  login_id: string;
  name: string;
  role: string;
  site_id: number | null;
  person_id: number | null;
}

interface SiteRow {
  id: number;
  site_name: string;
}

interface SafetyPerson {
  department_name: string | null;
  site_name: string | null;
}

interface SafetyDistribution {
  target_date: string;
  ack_status: string;
  start_signed_at: string | null;
  end_signed_at: string | null;
  items: Array<{ work_name: string }>;
}

interface SafetyFeedback {
  content: string;
  created_at: string;
}

interface SafetyRecord {
  person: SafetyPerson;
  distributions: SafetyDistribution[];
  feedbacks: SafetyFeedback[];
}

const users = ref<UserRow[]>([]);
const sites = ref<SiteRow[]>([]);
const loadingList = ref(false);
const loadingDetail = ref(false);
const keyword = ref("");
const selectedUserId = ref<number | null>(null);
const safetyRecord = ref<SafetyRecord | null>(null);
const hasSafetyData = ref(false);
const resettingPw = ref(false);

const selectedUser = computed(() => users.value.find((u) => u.id === selectedUserId.value) ?? null);
const filteredUsers = computed(() => {
  const q = keyword.value.trim().toLowerCase();
  if (!q) return users.value;
  return users.value.filter((u) => `${u.name} ${u.login_id}`.toLowerCase().includes(q));
});
const selectedSite = computed(() => sites.value.find((s) => s.id === selectedUser.value?.site_id) ?? null);
const latestDistribution = computed(() => safetyRecord.value?.distributions?.[0] ?? null);
const latestFeedback = computed(() => safetyRecord.value?.feedbacks?.[0] ?? null);

const siteNameLabel = computed(() => selectedSite.value?.site_name || safetyRecord.value?.person?.site_name || "데이터 없음");
const teamLabel = computed(() => {
  if (!hasSafetyData.value) return "연동 전";
  return safetyRecord.value?.person?.department_name || "데이터 없음";
});
const skillAndScoreLabel = computed(() => "연동 전");
const todayWorkLabel = computed(() => {
  if (!hasSafetyData.value) return "연동 전";
  if (!latestDistribution.value) return "데이터 없음";
  const workName = latestDistribution.value.items?.[0]?.work_name;
  return workName || "데이터 없음";
});
const attendanceLabel = computed(() => {
  if (!hasSafetyData.value) return "연동 전";
  if (!latestDistribution.value) return "데이터 없음";
  return latestDistribution.value.ack_status === "SIGNED" || latestDistribution.value.ack_status === "VIEWED"
    ? "출역"
    : "미확인";
});
const tbmSignLabel = computed(() => {
  if (!hasSafetyData.value) return "연동 전";
  if (!latestDistribution.value) return "데이터 없음";
  return latestDistribution.value.start_signed_at || latestDistribution.value.end_signed_at ? "서명 완료" : "미서명";
});
const recentDocumentLabel = computed(() => {
  if (!hasSafetyData.value) return "연동 전";
  if (!latestDistribution.value) return "데이터 없음";
  return `작업일: ${latestDistribution.value.target_date}`;
});
const recentFeedbackLabel = computed(() => {
  if (!hasSafetyData.value) return "연동 전";
  if (!latestFeedback.value) return "데이터 없음";
  return latestFeedback.value.content || "데이터 없음";
});

function roleLabel(role: string) {
  const map: Record<string, string> = {
    SUPER_ADMIN: "슈퍼관리자",
    HQ_SAFE: "본사 안전",
    HQ_SAFE_ADMIN: "본사 안전(관리)",
    HQ_OTHER: "본사 일반",
    SITE: "현장관리자",
    WORKER: "작업자",
  };
  return map[role] ?? role;
}

async function loadUsers() {
  loadingList.value = true;
  try {
    const [usersRes, sitesRes] = await Promise.all([api.get("/users"), api.get("/sites")]);
    users.value = usersRes.data;
    sites.value = sitesRes.data;
    if (selectedUserId.value == null && users.value.length > 0) {
      selectedUserId.value = users.value[0].id;
      await loadSelectedUserDetail();
    } else if (selectedUserId.value != null && !users.value.some((u) => u.id === selectedUserId.value)) {
      selectedUserId.value = users.value[0]?.id ?? null;
      if (selectedUserId.value != null) await loadSelectedUserDetail();
    }
  } finally {
    loadingList.value = false;
  }
}

async function loadSelectedUserDetail() {
  const personId = selectedUser.value?.person_id;
  hasSafetyData.value = false;
  safetyRecord.value = null;
  if (!personId) return;
  loadingDetail.value = true;
  try {
    const res = await api.get(`/hq-safe/workers/${personId}/safety-record`);
    safetyRecord.value = res.data;
    hasSafetyData.value = true;
  } catch {
    hasSafetyData.value = false;
  } finally {
    loadingDetail.value = false;
  }
}

async function selectUser(userId: number) {
  if (selectedUserId.value === userId) return;
  selectedUserId.value = userId;
  await loadSelectedUserDetail();
}

async function handleResetPassword() {
  if (!selectedUser.value) return;
  const u = selectedUser.value;
  if (!window.confirm(`${u.name} (${u.login_id}) 계정의 비밀번호를 초기화할까요?`)) return;
  resettingPw.value = true;
  try {
    const res = await api.post(`/users/${u.id}/admin-reset-password`);
    const temp = res.data.temporary_password as string;
    const msg = (res.data.message as string) || "";
    window.alert(`임시 비밀번호:\n${temp}\n\n${msg}`);
  } catch {
    window.alert("초기화에 실패했습니다.");
  } finally {
    resettingPw.value = false;
  }
}

onMounted(loadUsers);
</script>

<style scoped>
.user-mgmt-page {
  width: 100%;
}

.page-head {
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
}

.page-sub {
  margin: 6px 0 0;
  font-size: 14px;
  color: #64748b;
}

.user-mgmt-grid {
  display: grid;
  grid-template-columns: minmax(280px, 320px) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.search-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
}

.panel-state {
  color: #64748b;
  padding: 20px 0;
  font-size: 14px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.detail-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  background: #fff;
}

.detail-item span {
  color: #64748b;
  font-size: 13px;
}

.detail-item strong {
  color: #0f172a;
  font-size: 14px;
  text-align: right;
}

.kpi-user {
  margin-top: 8px;
}

.user-pw-reset {
  margin: 16px 0;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.user-pw-reset-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
}

@media (max-width: 1024px) {
  .user-mgmt-grid {
    grid-template-columns: 1fr;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
