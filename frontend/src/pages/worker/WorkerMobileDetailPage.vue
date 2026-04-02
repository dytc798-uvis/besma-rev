<template>
  <div class="mobile-shell">
    <div class="mobile-card">
      <h1>작업일보 상세/서명</h1>
      <div class="mobile-actions">
        <button class="mobile-secondary" @click="goList">목록으로</button>
        <button class="mobile-primary" :disabled="loading" @click="loadDetail">새로고침</button>
        <button v-if="auth.isAuthenticated" class="mobile-secondary" @click="handleLogout">로그아웃</button>
      </div>

      <section v-if="auth.user" class="status-box">
        <div><strong>계정:</strong> {{ auth.user.login_id }}</div>
      </section>

      <section v-if="offlineQueueEnabled" class="status-box">
        <div><strong>임시 저장 서명</strong></div>
        <div>대기 건수: {{ pendingQueue.length }}</div>
        <button class="mobile-secondary" :disabled="loading || pendingQueue.length === 0" @click="resendPendingSigns">
          미전송 서명 재전송
        </button>
      </section>

      <p v-if="message" :class="['mobile-message', messageType]">{{ message }}</p>

      <section v-if="detail" class="status-box">
        <div><strong>배포:</strong> #{{ detail.distribution_id }}</div>
        <div><strong>상태:</strong> {{ ackStatusLabel(detail.ack_status) }}</div>
        <div><strong>시작서명:</strong> {{ detail.start_signed_at ?? "-" }}</div>
        <div><strong>종료서명:</strong> {{ detail.end_signed_at ?? "-" }}</div>
        <div v-if="detail.is_reassignment"><strong>작업 변경:</strong> {{ detail.reassignment_reason ?? "변경 작업 재고지" }}</div>
      </section>

      <section v-if="detail?.plan" class="content-box">
        <h2>작업 내용 확인</h2>
        <div class="plan-summary">
          <div><strong>작업일:</strong> {{ detail.plan.work_date }}</div>
          <div><strong>현장 ID:</strong> {{ detail.plan.site_id }}</div>
          <div><strong>계획 상태:</strong> 작업 준비중</div>
        </div>

        <div v-for="(item, idx) in detail.plan.items" :key="idx" class="work-item-card">
          <div class="work-item-title">작업 {{ idx + 1 }}</div>
          <div><strong>작업명:</strong> {{ item.work_name }}</div>
          <div><strong>작업내용:</strong> {{ item.work_description }}</div>
          <div><strong>팀:</strong> {{ item.team_label || "-" }}</div>

          <table class="risk-table">
            <thead>
              <tr>
                <th>위험요인</th>
                <th>대책</th>
                <th>위험도</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(risk, riskIdx) in item.risks" :key="riskIdx">
                <td>{{ risk.risk_factor }}</td>
                <td>{{ risk.counterplan }}</td>
                <td>{{ risk.risk_level }}</td>
              </tr>
              <tr v-if="item.risks.length === 0">
                <td colspan="3">등록된 위험요인/대책이 없습니다.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="sign-box">
        <h2>시작 서명</h2>
        <SignaturePad ref="startPadRef" :height="220" />
        <button class="mobile-primary" :disabled="loading || !canSignStart" @click="signStart">
          시작 서명 제출
        </button>
      </section>

      <section class="sign-box">
        <h2>종료 서명</h2>
        <label class="mobile-field">
          <span>종료 상태</span>
          <select v-model="endStatus">
            <option value="NORMAL">NORMAL</option>
            <option value="ISSUE">ISSUE</option>
          </select>
        </label>
        <SignaturePad ref="endPadRef" :height="220" />
        <button class="mobile-primary" :disabled="loading || !canSignEnd" @click="signEnd">
          종료 서명 제출
        </button>
      </section>

      <section class="sign-box">
        <h2>현장 위험/특이사항 제보</h2>
        <label class="mobile-field">
          <span>분류</span>
          <select v-model="feedbackType">
            <option value="risk">위험 제보</option>
            <option value="incident">사건/이상 징후</option>
            <option value="suggestion">개선 제안</option>
            <option value="other">기타</option>
          </select>
        </label>
        <label class="mobile-field">
          <span>연결 작업</span>
          <select v-model="feedbackPlanItemId">
            <option :value="null">전체 작업 흐름</option>
            <option v-for="(item, idx) in detail?.plan.items ?? []" :key="item.plan_item_id ?? idx" :value="item.plan_item_id ?? null">
              {{ idx + 1 }}. {{ item.work_name }}
            </option>
          </select>
        </label>
        <label class="mobile-field">
          <span>내용</span>
          <textarea v-model="feedbackContent" rows="4" placeholder="작업 중 발견한 위험, 특이사항, 개선 제안을 입력하세요." />
        </label>
        <button class="mobile-primary" :disabled="loading || !feedbackContent.trim()" @click="submitFeedback">
          제보 등록
        </button>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/services/api";
import SignaturePad from "@/components/SignaturePad.vue";
import { useAuthStore } from "@/stores/auth";
import {
  enqueuePendingSign,
  getPendingSignQueue,
  isOfflineSignQueueEnabled,
  removePendingSignQueueItems,
  type PendingSignQueueItem,
} from "@/services/offlineSignQueue";

interface WorkerPlanDetail {
  distribution_id: number;
  is_reassignment?: boolean;
  reassignment_reason?: string | null;
  ack_status: string;
  start_signed_at: string | null;
  end_signed_at: string | null;
  plan: {
    site_id: number;
    work_date: string;
    status: string;
    items: Array<{
      plan_item_id?: number | null;
      work_name: string;
      work_description: string;
      team_label: string | null;
      risks: Array<{
        risk_factor: string;
        counterplan: string;
        risk_level: number;
      }>;
    }>;
  };
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const distributionId = Number(route.params.distributionId);
const accessToken = ref<string>((route.query.access_token as string) || "");
const loading = ref(false);
const detail = ref<WorkerPlanDetail | null>(null);
const message = ref("");
const messageType = ref<"error" | "success">("error");
const endStatus = ref<"NORMAL" | "ISSUE">("NORMAL");
const startPadRef = ref<InstanceType<typeof SignaturePad> | null>(null);
const endPadRef = ref<InstanceType<typeof SignaturePad> | null>(null);
const offlineQueueEnabled = isOfflineSignQueueEnabled();
const pendingQueue = ref<PendingSignQueueItem[]>([]);
const feedbackType = ref("risk");
const feedbackContent = ref("");
const feedbackPlanItemId = ref<number | null>(null);

const canSignStart = computed(() => !!detail.value && !detail.value.start_signed_at);
const canSignEnd = computed(() => !!detail.value?.start_signed_at && !detail.value?.end_signed_at);

function goList() {
  router.push({
    name: "worker-mobile-list",
    query: accessToken.value ? { access_token: accessToken.value } : undefined,
  });
}

function handleLogout() {
  auth.logout();
  router.push({ name: "login" });
}

async function getCurrentLocation(): Promise<{ lat: number; lng: number }> {
  if (!navigator.geolocation) return { lat: 0, lng: 0 };
  try {
    const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 10000,
      });
    });
    return { lat: pos.coords.latitude, lng: pos.coords.longitude };
  } catch {
    return { lat: 0, lng: 0 };
  }
}

function setError(text: string) {
  messageType.value = "error";
  message.value = text;
}

function setSuccess(text: string) {
  messageType.value = "success";
  message.value = text;
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

function refreshPendingQueue() {
  if (!offlineQueueEnabled) {
    pendingQueue.value = [];
    return;
  }
  pendingQueue.value = getPendingSignQueue().sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

async function loadDetail() {
  loading.value = true;
  message.value = "";
  try {
    const params = accessToken.value ? { access_token: accessToken.value } : undefined;
    const res = await api.get(`/worker/my-daily-work-plans/${distributionId}`, {
      params,
    });
    detail.value = res.data;
  } catch (err: any) {
    setError(err?.response?.data?.detail ?? "상세 조회 중 오류가 발생했습니다.");
  } finally {
    loading.value = false;
  }
}

async function signStart() {
  loading.value = true;
  message.value = "";
  let signatureData = "";
  let lat = 0;
  let lng = 0;
  const timestamp = new Date().toISOString();
  try {
    signatureData = startPadRef.value?.toDataUrl() || "";
    if (!signatureData) throw new Error("서명을 입력하세요.");
    ({ lat, lng } = await getCurrentLocation());
    const payload: Record<string, unknown> = {
      signature_data: signatureData,
      signature_mime: "image/png",
      lat,
      lng,
    };
    if (accessToken.value) payload.access_token = accessToken.value;
    const res = await api.post(`/worker/my-daily-work-plans/${distributionId}/sign-start`, payload);
    detail.value = { ...(detail.value as WorkerPlanDetail), ...res.data };
    setSuccess(res.data?.message ?? "시작 서명이 완료되었습니다.");
  } catch (err: any) {
    if (offlineQueueEnabled && axios.isAxiosError(err) && !err.response) {
      try {
        enqueuePendingSign({
          distribution_id: distributionId,
          access_token: accessToken.value || null,
          sign_type: "start",
          lat,
          lng,
          timestamp,
          signature_data: signatureData,
          signature_mime: "image/png",
        });
        refreshPendingQueue();
        setError("네트워크가 끊겨 서명 데이터를 임시 저장했습니다. 연결 후 재전송하세요.");
      } catch {
        setError("시작 서명에 실패했습니다.");
      }
    } else {
      const text = err?.response?.data?.detail ?? err?.message ?? "시작 서명에 실패했습니다.";
      setError(text);
    }
  } finally {
    loading.value = false;
  }
}

async function signEnd() {
  loading.value = true;
  message.value = "";
  let signatureData = "";
  let lat = 0;
  let lng = 0;
  const timestamp = new Date().toISOString();
  try {
    signatureData = endPadRef.value?.toDataUrl() || "";
    if (!signatureData) throw new Error("서명을 입력하세요.");
    ({ lat, lng } = await getCurrentLocation());
    const payload: Record<string, unknown> = {
      end_status: endStatus.value,
      signature_data: signatureData,
      signature_mime: "image/png",
      lat,
      lng,
    };
    if (accessToken.value) payload.access_token = accessToken.value;
    const res = await api.post(`/worker/my-daily-work-plans/${distributionId}/sign-end`, payload);
    detail.value = { ...(detail.value as WorkerPlanDetail), ...res.data };
    setSuccess("종료 서명이 완료되었습니다.");
  } catch (err: any) {
    if (offlineQueueEnabled && axios.isAxiosError(err) && !err.response) {
      try {
        enqueuePendingSign({
          distribution_id: distributionId,
          access_token: accessToken.value || null,
          sign_type: "end",
          lat,
          lng,
          timestamp,
          signature_data: signatureData,
          signature_mime: "image/png",
          end_status: endStatus.value,
        });
        refreshPendingQueue();
        setError("네트워크가 끊겨 서명 데이터를 임시 저장했습니다. 연결 후 재전송하세요.");
      } catch {
        setError("종료 서명에 실패했습니다.");
      }
    } else {
      const text = err?.response?.data?.detail ?? err?.message ?? "종료 서명에 실패했습니다.";
      setError(text);
    }
  } finally {
    loading.value = false;
  }
}

async function submitFeedback() {
  if (!feedbackContent.value.trim()) return;
  loading.value = true;
  message.value = "";
  try {
    const payload: Record<string, unknown> = {
      feedback_type: feedbackType.value,
      content: feedbackContent.value.trim(),
    };
    if (feedbackPlanItemId.value) payload.plan_item_id = feedbackPlanItemId.value;
    if (accessToken.value) payload.access_token = accessToken.value;
    await api.post(`/worker/my-daily-work-plans/${distributionId}/feedback`, payload);
    feedbackContent.value = "";
    feedbackPlanItemId.value = null;
    feedbackType.value = "risk";
    setSuccess("현장 제보가 등록되었습니다.");
  } catch (err: any) {
    setError(err?.response?.data?.detail ?? "제보 등록에 실패했습니다.");
  } finally {
    loading.value = false;
  }
}

async function resendPendingSigns() {
  if (!offlineQueueEnabled) return;
  loading.value = true;
  message.value = "";
  refreshPendingQueue();
  const queue = [...pendingQueue.value];
  if (queue.length === 0) {
    setSuccess("재전송할 임시 서명이 없습니다.");
    loading.value = false;
    return;
  }

  const successIds: string[] = [];
  for (const item of queue) {
    try {
      if (item.sign_type === "start") {
        const payload: Record<string, unknown> = {
          signature_data: item.signature_data,
          signature_mime: item.signature_mime,
          lat: item.lat,
          lng: item.lng,
        };
        if (item.access_token) payload.access_token = item.access_token;
        await api.post(`/worker/my-daily-work-plans/${item.distribution_id}/sign-start`, payload);
      } else {
        const payload: Record<string, unknown> = {
          end_status: item.end_status,
          signature_data: item.signature_data,
          signature_mime: item.signature_mime,
          lat: item.lat,
          lng: item.lng,
        };
        if (item.access_token) payload.access_token = item.access_token;
        await api.post(`/worker/my-daily-work-plans/${item.distribution_id}/sign-end`, payload);
      }
      successIds.push(item.id);
    } catch (err: any) {
      removePendingSignQueueItems(successIds);
      refreshPendingQueue();
      const detail = err?.response?.data?.detail;
      setError(detail || "재전송에 실패했습니다. 위치와 네트워크 상태를 다시 확인하세요.");
      loading.value = false;
      return;
    }
  }

  removePendingSignQueueItems(successIds);
  refreshPendingQueue();
  setSuccess("임시 저장된 서명이 정상 전송되었습니다.");
  await loadDetail();
  loading.value = false;
}

onMounted(() => {
  refreshPendingQueue();
  if (Number.isFinite(distributionId) && distributionId > 0) {
    loadDetail();
  } else {
    setError("배포 정보가 올바르지 않습니다. 링크를 다시 확인하세요.");
  }
});
</script>

<style scoped>
.mobile-shell {
  min-height: 100vh;
  padding: 12px;
  background: #f3f4f6;
}

.mobile-card {
  max-width: 720px;
  margin: 0 auto;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

h1 {
  margin: 0 0 10px;
  font-size: 20px;
}

h2 {
  font-size: 16px;
  margin: 0 0 8px;
}

.mobile-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mobile-field input,
.mobile-field select,
.mobile-field textarea {
  height: 42px;
  font-size: 16px;
}

.mobile-field textarea {
  min-height: 96px;
  padding: 10px;
  resize: vertical;
}

.mobile-actions {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin: 10px 0 12px;
}

.mobile-primary,
.mobile-secondary {
  width: 100%;
  min-height: 46px;
  border: none;
  border-radius: 10px;
  font-size: 16px;
}

.mobile-primary {
  background: #2563eb;
  color: #fff;
}

.mobile-secondary {
  background: #e5e7eb;
}

@media (max-width: 720px) {
  .mobile-actions {
    grid-template-columns: 1fr;
  }
}

.mobile-message {
  margin: 8px 0;
  font-weight: 600;
}

.mobile-message.error {
  color: #dc2626;
}

.mobile-message.success {
  color: #16a34a;
}

.status-box {
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 12px;
  display: grid;
  gap: 4px;
}

.content-box {
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
  display: grid;
  gap: 10px;
}

.plan-summary {
  display: grid;
  gap: 4px;
}

.work-item-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  display: grid;
  gap: 6px;
  background: #fafafa;
}

.work-item-title {
  font-weight: 700;
}

.risk-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.risk-table th,
.risk-table td {
  border: 1px solid #d1d5db;
  padding: 6px;
  vertical-align: top;
  text-align: left;
}

.sign-box {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 12px;
  display: grid;
  gap: 8px;
}
</style>
