<template>
  <div class="card">
    <div class="card-title">미결재 문서</div>
    <div class="toolbar">
      <div class="toolbar-filters">
        <select v-model="statusFilter">
          <option value="">전체</option>
          <option value="SUBMITTED">제출</option>
          <option value="UNDER_REVIEW">검토중</option>
          <option value="RESUBMITTED">재제출</option>
        </select>
      </div>
      <div class="toolbar-actions">
        <button class="secondary" @click="load">조회</button>
      </div>
    </div>
    <table class="basic-table">
      <thead>
        <tr>
          <th>문서번호</th>
          <th>제목</th>
          <th>현장</th>
          <th>상태</th>
          <th>제출일</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="doc in documents"
          :key="doc.id"
          @click="goDetail(doc.id)"
          style="cursor: pointer"
        >
          <td>{{ doc.document_no }}</td>
          <td>{{ doc.title }}</td>
          <td>{{ doc.site_id }}</td>
          <td>
            <span class="badge" :class="`badge-status-${doc.current_status}`">
              {{ doc.current_status }}
            </span>
          </td>
          <td>{{ doc.submitted_at ? doc.submitted_at.slice(0, 10) : "-" }}</td>
        </tr>
        <tr v-if="documents.length === 0">
          <td colspan="5" style="text-align: center; color: #6b7280">데이터가 없습니다.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";

interface DocumentItem {
  id: number;
  document_no: string;
  title: string;
  site_id: number;
  current_status: string;
  submitted_at: string | null;
}

const documents = ref<DocumentItem[]>([]);
const statusFilter = ref("SUBMITTED");
const router = useRouter();

async function load() {
  const res = await api.get("/documents", {
    params: {
      status_filter: statusFilter.value || undefined,
    },
  });
  documents.value = res.data;
}

function goDetail(id: number) {
  router.push({ name: "hq-safe-document-detail", params: { id } });
}

onMounted(load);
</script>

