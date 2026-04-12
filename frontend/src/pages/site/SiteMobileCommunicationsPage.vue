<template>
  <div class="mobile-wrap">
    <div class="card">
      <div class="card-title">소통자료 업로드</div>
      <p class="helper">사진 1장 이상을 선택하고 수신자를 고른 뒤 전송하세요. 업로드된 이미지는 서버에서 자동 최적화되며, 여러 장이면 PDF도 함께 생성됩니다.</p>

      <div class="field">
        <label>사진</label>
        <input type="file" accept="image/*" multiple capture="environment" @change="onFileChange" />
      </div>
      <div class="field">
        <label>제목 (선택)</label>
        <input v-model="title" type="text" placeholder="예) 작업 전 현장 상태" />
      </div>
      <div class="field">
        <label>설명 (선택)</label>
        <textarea v-model="description" rows="3" placeholder="필요 시 간단히 작성" />
      </div>
      <div class="field">
        <label>수신자</label>
        <div v-if="receivers.length === 0" class="empty">선택 가능한 수신자가 없습니다.</div>
        <label v-for="u in receivers" :key="u.id" class="check-row">
          <input type="checkbox" :value="u.id" v-model="selectedReceiverIds" />
          <span>{{ u.name }} ({{ u.login_id }})</span>
        </label>
      </div>

      <button class="primary submit-btn" type="button" @click="submit" :disabled="submitting">
        {{ submitting ? "전송 중..." : "소통자료 전송" }}
      </button>
      <p v-if="message" class="message">{{ message }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/services/api";

interface ReceiverOption {
  id: number;
  name: string;
  login_id: string;
}

const title = ref("");
const description = ref("");
const files = ref<File[]>([]);
const receivers = ref<ReceiverOption[]>([]);
const selectedReceiverIds = ref<number[]>([]);
const submitting = ref(false);
const message = ref("");

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  files.value = target.files ? Array.from(target.files) : [];
}

async function loadReceivers() {
  const res = await api.get("/communications/receivers");
  receivers.value = (res.data ?? []) as ReceiverOption[];
}

async function submit() {
  message.value = "";
  if (files.value.length === 0) {
    message.value = "사진을 1장 이상 선택해 주세요.";
    return;
  }
  if (selectedReceiverIds.value.length === 0) {
    message.value = "수신자를 1명 이상 선택해 주세요.";
    return;
  }
  const form = new FormData();
  if (title.value.trim()) form.append("title", title.value.trim());
  if (description.value.trim()) form.append("description", description.value.trim());
  selectedReceiverIds.value.forEach((id) => form.append("receiver_user_ids", String(id)));
  files.value.forEach((file) => form.append("files", file));

  submitting.value = true;
  try {
    await api.post("/communications", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    title.value = "";
    description.value = "";
    files.value = [];
    selectedReceiverIds.value = [];
    message.value = "전송되었습니다.";
  } catch {
    message.value = "전송에 실패했습니다. 다시 시도해 주세요.";
  } finally {
    submitting.value = false;
  }
}

onMounted(loadReceivers);
</script>

<style scoped>
.mobile-wrap {
  max-width: 760px;
  margin: 0 auto;
  padding: 8px;
}
.helper {
  margin-top: 6px;
  color: #64748b;
  font-size: 13px;
}
.field {
  margin-top: 10px;
}
.field label {
  display: block;
  font-size: 13px;
  color: #334155;
  margin-bottom: 6px;
}
.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.submit-btn {
  margin-top: 12px;
}
.message {
  margin-top: 10px;
  font-size: 13px;
  color: #334155;
}
.empty {
  color: #94a3b8;
  font-size: 13px;
}
</style>

