<template>
  <div class="card">
    <div class="card-title">승인 / 반려 이력</div>
    <div class="toolbar">
      <div class="toolbar-filters">
        <input v-model="documentId" type="text" placeholder="문서 ID 필터" />
      </div>
      <div class="toolbar-actions">
        <button class="secondary" @click="load">조회</button>
      </div>
    </div>
    <table class="basic-table">
      <thead>
        <tr>
          <th>문서 ID</th>
          <th>액션</th>
          <th>사용자</th>
          <th>코멘트</th>
          <th>일시</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="h in histories" :key="h.id">
          <td>{{ h.document_id }}</td>
          <td>{{ h.action_type }}</td>
          <td>{{ h.action_by_user_id }}</td>
          <td>{{ h.comment }}</td>
          <td>{{ h.action_at.slice(0, 19).replace('T', ' ') }}</td>
        </tr>
        <tr v-if="histories.length === 0">
          <td colspan="5" style="text-align: center; color: #6b7280">데이터가 없습니다.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/services/api";

interface HistoryItem {
  id: number;
  document_id: number;
  action_type: string;
  action_by_user_id: number;
  comment: string | null;
  action_at: string;
}

const histories = ref<HistoryItem[]>([]);
const documentId = ref("");

async function load() {
  const res = await api.get("/approvals/history", {
    params: {
      document_id: documentId.value || undefined,
    },
  });
  histories.value = res.data;
}

onMounted(load);
</script>

