<template>
  <section v-if="showSection" class="reward-inline panel">
    <div class="reward-inline-head">
      <h3>고객사 포상</h3>
    </div>
    <p class="reward-hint">
      포상 사진을 올리면 본사 승인 후 비고에 「고객사포상(+5)」이 표시됩니다. 제출 후에는 회수·변경할 수 없습니다.
    </p>

    <ul v-if="rewardHistory.length" class="reward-history">
      <li v-for="r in rewardHistory" :key="r.id">
        <span class="reward-status">{{ rewardStatusLabel(r.status) }}</span>
        <span v-if="r.status === 'APPROVED'" class="muted">+{{ r.bonus_points ?? 5 }}점</span>
        <button class="link-btn" type="button" @click="previewRewardPhoto(r.id)">사진 보기</button>
      </li>
    </ul>

    <p v-if="blockedReason" class="reward-blocked">{{ blockedReason }}</p>

    <template v-else-if="canUpload">
      <label class="field">
        <span class="field-label">포상 사진</span>
        <input ref="photoInputRef" type="file" accept="image/jpeg,image/png,image/webp" class="field-control" @change="onPhotoChange" />
      </label>
      <div v-if="previewUrl" class="reward-preview">
        <img :src="previewUrl" alt="선택한 포상 사진 미리보기" />
      </div>
      <div class="actions">
        <button
          v-if="showCancel"
          class="stitch-btn-secondary touch-btn"
          type="button"
          :disabled="uploading"
          @click="emit('cancel')"
        >
          취소
        </button>
        <button
          class="stitch-btn-primary touch-btn"
          type="button"
          :disabled="!photoFile || uploading || rewardHasSubmitted"
          @click="submitUpload"
        >
          {{ uploading ? "제출 중…" : rewardHasSubmitted ? "제출 완료" : "본사 승인 요청" }}
        </button>
      </div>
    </template>

    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api } from "@/services/api";

interface Worker {
  id: number;
  name: string;
  eval_assignment?: "DIRECT" | "TEAM" | "TEAM_LEADER";
  is_permanently_expelled?: boolean;
  customer_reward?: { id: number; status: string; bonus_points?: number } | null;
}

const props = withDefaults(
  defineProps<{
    worker: Worker;
    periodClosed: boolean;
    evidenceSubmitBlocked?: boolean;
    evaluationLocked?: boolean;
    showCancel?: boolean;
  }>(),
  {
    evidenceSubmitBlocked: false,
    evaluationLocked: false,
    showCancel: false,
  },
);

const emit = defineEmits<{ saved: []; cancel: [] }>();

const photoFile = ref<File | null>(null);
const photoInputRef = ref<HTMLInputElement | null>(null);
const previewUrl = ref<string | null>(null);
const uploading = ref(false);
const error = ref("");
const rewardHistory = ref<Array<{ id: number; status: string; bonus_points?: number }>>([]);

const rewardHasSubmitted = computed(() => rewardHistory.value.length > 0);

const blockedReason = computed(() => {
  if (props.worker.is_permanently_expelled) return "영구 퇴출 대상자는 포상을 등록할 수 없습니다.";
  if (props.evidenceSubmitBlocked) return "승인 진행 중에는 포상·제재를 변경할 수 없습니다.";
  return null;
});

const canUpload = computed(() => {
  if (blockedReason.value) return false;
  if (props.worker.customer_reward) return false;
  return true;
});

const showSection = computed(() => {
  if (props.worker.customer_reward || rewardHistory.value.length) return true;
  if (blockedReason.value) return true;
  return canUpload.value;
});

function rewardStatusLabel(status: string): string {
  if (status === "APPROVED") return "승인";
  if (status === "PENDING") return "승인 대기";
  if (status === "REJECTED") return "반려";
  return status;
}

function clearPreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = null;
  }
}

function resetForm() {
  photoFile.value = null;
  error.value = "";
  clearPreview();
  if (photoInputRef.value) photoInputRef.value.value = "";
}

async function loadHistory() {
  try {
    const res = await api.get(`/functional-eval/workers/${props.worker.id}/customer-rewards`);
    rewardHistory.value = res.data.items || [];
  } catch {
    rewardHistory.value = [];
  }
}

async function previewRewardPhoto(rewardId: number) {
  try {
    const res = await api.get(`/functional-eval/customer-rewards/${rewardId}/photo`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch {
    error.value = "사진을 불러오지 못했습니다.";
  }
}

function onPhotoChange(e: Event) {
  const input = e.target as HTMLInputElement;
  photoFile.value = input.files?.[0] ?? null;
  clearPreview();
  if (photoFile.value) {
    previewUrl.value = URL.createObjectURL(photoFile.value);
  }
}

async function submitUpload() {
  if (!photoFile.value || rewardHasSubmitted.value) return;
  uploading.value = true;
  error.value = "";
  try {
    const fd = new FormData();
    fd.append("photo", photoFile.value);
    await api.post(`/functional-eval/workers/${props.worker.id}/customer-rewards`, fd, {
      params: { bonus_points: 5 },
      headers: { "Content-Type": "multipart/form-data" },
    });
    resetForm();
    await loadHistory();
    emit("saved");
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof detail === "string" ? detail : "포상 사진 제출에 실패했습니다.";
  } finally {
    uploading.value = false;
  }
}

watch(
  () => props.worker.id,
  () => {
    resetForm();
    void loadHistory();
  },
  { immediate: true },
);
</script>

<style scoped>
.reward-inline {
  margin-top: 12px;
  padding: 14px 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.reward-inline-head h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.reward-hint {
  margin: 0 0 10px;
  padding: 10px 12px;
  background: #eff6ff;
  border: 1px solid #93c5fd;
  border-radius: 8px;
  color: #1e40af;
  font-size: 13px;
  line-height: 1.45;
}

.reward-blocked {
  margin: 0;
  font-size: 13px;
  color: #64748b;
}

.reward-history {
  margin: 0 0 12px;
  padding: 0;
  list-style: none;
  font-size: 13px;
}

.reward-history li {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

.reward-status {
  font-weight: 600;
  color: #0f172a;
}

.field {
  display: block;
  margin-top: 8px;
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}

.field-control {
  width: 100%;
  box-sizing: border-box;
  font-size: 14px;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
}

.reward-preview {
  margin-top: 10px;
}

.reward-preview img {
  max-width: 100%;
  max-height: 220px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  object-fit: contain;
  background: #f8fafc;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}

.error {
  color: #b91c1c;
  margin-top: 10px;
  font-size: 13px;
}

.muted {
  color: #64748b;
  font-size: 12px;
}

.link-btn {
  background: none;
  border: none;
  color: #2563eb;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}
</style>
