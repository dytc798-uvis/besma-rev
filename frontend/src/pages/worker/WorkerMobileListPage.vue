<template>
  <div class="mobile-shell">
    <div class="mobile-card">
      <h1>근로자 작업일보</h1>
      <div class="mobile-actions">
        <button class="mobile-primary" :disabled="loading" @click="loadMyPlans">
          {{ loading ? "조회 중..." : "내 배포 목록 조회" }}
        </button>
        <button v-if="auth.isAuthenticated" class="mobile-secondary" @click="handleLogout">로그아웃</button>
      </div>
      <section v-if="auth.user" class="status-box">
        <div><strong>계정:</strong> {{ auth.user.login_id }}</div>
      </section>
      <p v-if="message" class="mobile-message">{{ message }}</p>
      <ul class="mobile-list" v-if="plans.length > 0">
        <li v-for="item in plans" :key="item.distribution_id">
          <div><strong>배포 #{{ item.distribution_id }}</strong></div>
          <div>작업일: {{ item.work_date }}</div>
          <div>상태: {{ ackStatusLabel(item.ack_status) }}</div>
          <div v-if="item.is_reassignment" class="reassign-flag">작업 변경 재지시 도착</div>
          <button class="mobile-secondary" @click="goDetail(item.distribution_id)">상세/서명</button>
        </li>
      </ul>
      <section v-else-if="!loading" class="status-box">
        <div><strong>조회 결과</strong></div>
        <div v-if="!auth.isAuthenticated && !accessToken">접근 권한이 없습니다.</div>
        <div v-else>표시할 배포가 없습니다.</div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

interface WorkerPlanItem {
  distribution_id: number;
  work_date: string;
  ack_status: string;
  is_reassignment?: boolean;
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const accessToken = ref<string>((route.query.access_token as string) || "");
const plans = ref<WorkerPlanItem[]>([]);
const loading = ref(false);
const message = ref("");

async function loadMyPlans() {
  loading.value = true;
  message.value = "";
  try {
    if (!accessToken.value && auth.isAuthenticated && !auth.user?.person_id) {
      plans.value = [];
      message.value = "조회할 수 없습니다.";
      return;
    }
    const params = accessToken.value ? { access_token: accessToken.value } : undefined;
    const res = await api.get("/worker/my-daily-work-plans", { params });
    plans.value = res.data;
    if (plans.value.length === 0) {
      message.value = "표시할 배포가 없습니다.";
    }
  } catch {
    message.value = "요청을 처리할 수 없습니다.";
  } finally {
    loading.value = false;
  }
}

function goDetail(distributionId: number) {
  router.push({
    name: "worker-mobile-detail",
    params: { distributionId },
    query: accessToken.value ? { access_token: accessToken.value } : undefined,
  });
}

function handleLogout() {
  auth.logout();
  router.push({ name: "login" });
}

function ackStatusLabel(status: string) {
  const map: Record<string, string> = {
    PENDING: "확인 필요",
    VIEWED: "작업 준비중",
    START_SIGNED: "작업중",
    COMPLETED: "완료",
  };
  return map[status] ?? status;
}

if (auth.isAuthenticated || accessToken.value) {
  loadMyPlans();
}
</script>

<style scoped>
.mobile-shell {
  min-height: 100vh;
  padding: 12px;
  background: #f3f4f6;
}

.mobile-card {
  max-width: 560px;
  margin: 0 auto;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

h1 {
  margin: 0 0 6px;
  font-size: 20px;
}

.helper {
  margin: 0 0 12px;
  color: #6b7280;
  font-size: 13px;
}

.mobile-actions {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}

.mobile-primary,
.mobile-secondary {
  width: 100%;
  min-height: 44px;
  border: none;
  border-radius: 10px;
  font-size: 16px;
}

.mobile-primary {
  background: #2563eb;
  color: #fff;
}

.mobile-secondary {
  margin-top: 8px;
  background: #e5e7eb;
}

.mobile-message {
  margin-top: 10px;
  color: #ef4444;
  font-size: 14px;
}

.status-box {
  margin-top: 12px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 10px;
  display: grid;
  gap: 4px;
}

.mobile-list {
  list-style: none;
  padding: 0;
  margin: 12px 0 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mobile-list li {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  background: #fafafa;
}

.reassign-flag {
  margin-top: 4px;
  color: #b45309;
  font-weight: 600;
}

@media (max-width: 720px) {
  .mobile-actions {
    grid-template-columns: 1fr;
  }
}
</style>
