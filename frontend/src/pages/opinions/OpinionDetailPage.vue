<template>
  <div class="card" v-if="opinion">
    <div class="card-title" style="display: flex; align-items: center; justify-content: space-between; gap: 12px">
      <span>운영 아이디어 상세 / 조치</span>
      <button
        v-if="canDelete"
        type="button"
        class="secondary danger-btn"
        :disabled="deleting"
        @click="deleteOpinion"
      >
        {{ deleting ? "삭제 중…" : "삭제" }}
      </button>
    </div>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; font-size: 13px">
      <div><strong>ID</strong> {{ opinion.id }}</div>
      <div><strong>제안자</strong> {{ opinion.reporter_type }}</div>
      <div><strong>유형</strong> {{ opinion.category }}</div>
      <div><strong>상태</strong> {{ opinionStatusLabel(opinion.status) }}</div>
      <div style="grid-column: span 2">
        <strong>아이디어</strong>
        <div>{{ opinion.content }}</div>
      </div>
      <div style="grid-column: span 2">
        <strong>조치내용</strong>
        <div>{{ opinion.action_result ?? "-" }}</div>
      </div>
    </div>

    <div style="margin-top: 16px">
      <h3 style="font-size: 14px; margin-bottom: 8px">상태 / 조치 업데이트</h3>
      <form class="form-grid" @submit.prevent="update">
        <div class="form-field">
          <label>상태</label>
          <select v-model="status">
            <option value="RECEIVED">검토전</option>
            <option value="REVIEWING">검토중</option>
            <option value="ACTIONED">조치완료</option>
            <option value="HOLD">보류</option>
          </select>
        </div>
        <div class="form-field" style="grid-column: span 2">
          <label>조치내용</label>
          <textarea v-model="actionResult" rows="3" />
        </div>
        <div style="grid-column: span 2; display: flex; justify-content: flex-end; gap: 8px">
          <button type="submit" class="primary">저장</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { opinionStatusLabel } from "@/utils/opinionStatus";

interface OpinionDetail {
  id: number;
  site_id: number;
  category: string;
  content: string;
  reporter_type: string;
  status: string;
  action_result: string | null;
  created_by_user_id?: number | null;
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const opinion = ref<OpinionDetail | null>(null);
const deleting = ref(false);
const status = ref("RECEIVED");
const actionResult = ref("");

const canDelete = computed(() => {
  const o = opinion.value;
  if (!o) return false;
  const role = auth.user?.role ?? "";
  const isAdmin = role === "HQ_SAFE_ADMIN" || role === "SUPER_ADMIN";
  if (isAdmin) return true;
  const aid = o.created_by_user_id;
  if (aid == null) return false;
  return Number(auth.user?.id ?? 0) === Number(aid);
});

function opinionsListRouteName() {
  const n = route.name?.toString() ?? "";
  if (n.startsWith("hq-safe")) return "hq-safe-opinions";
  if (n.startsWith("site-")) return "site-opinions";
  if (n.startsWith("hq-other")) return "hq-other-opinions";
  return "hq-safe-opinions";
}

async function deleteOpinion() {
  if (!opinion.value || !canDelete.value) return;
  if (!window.confirm("이 운영 아이디어 제안을 삭제할까요?\n삭제 후에는 복구할 수 없습니다.")) return;
  deleting.value = true;
  try {
    const id = opinion.value.id;
    await api.delete(`/opinions/${id}`);
    await router.push({ name: opinionsListRouteName() });
  } catch {
    window.alert("삭제에 실패했습니다.");
  } finally {
    deleting.value = false;
  }
}

async function load() {
  const res = await api.get(`/opinions/${route.params.id}`);
  opinion.value = res.data;
  status.value = opinion.value.status;
  actionResult.value = opinion.value.action_result ?? "";
}

async function update() {
  if (!opinion.value) return;
  await api.put(`/opinions/${opinion.value.id}`, {
    status: status.value,
    action_result: actionResult.value,
  });
  await load();
}

onMounted(load);
</script>

<style scoped>
.danger-btn {
  color: #b91c1c;
  border-color: #fecaca;
}
.danger-btn:hover:not(:disabled) {
  background: #fef2f2;
}
</style>
