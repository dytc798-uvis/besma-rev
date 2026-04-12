<template>
  <div class="card">
    <div class="header-row">
      <div class="card-title">안전 점검</div>
      <button class="secondary" @click="load">새로고침</button>
    </div>
    <table class="basic-table">
      <thead>
        <tr>
          <th>제목</th>
          <th>업로드시각</th>
          <th>파일</th>
          <th>코멘트</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="row.document_id">
          <td>{{ row.title }}</td>
          <td>{{ formatDateTime(row.uploaded_at) }}</td>
          <td><a :href="resolveUrl(row.file_url)" target="_blank" rel="noopener">보기</a></td>
          <td>
            <div class="comment-list">
              <p v-for="c in row.comments" :key="c.id">- {{ c.body }} ({{ c.created_by_name || "-" }})</p>
            </div>
            <div class="comment-write">
              <input v-model="drafts[row.document_id]" type="text" placeholder="코멘트 입력" />
              <button class="secondary" @click="addComment(row.document_id)">등록</button>
            </div>
          </td>
        </tr>
        <tr v-if="items.length === 0"><td colspan="4" style="text-align:center;color:#64748b">점검 파일이 없습니다.</td></tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/services/api";
import { formatDateTimeKst } from "@/utils/datetime";

const items = ref<any[]>([]);
const drafts = ref<Record<number, string>>({});
function resolveUrl(path: string) { return `${api.defaults.baseURL}${path}`; }
function formatDateTime(v?: string) {
  return formatDateTimeKst(v, "-");
}
async function load() { const res = await api.get("/safety-features/inspections"); items.value = res.data.items ?? []; }
async function addComment(documentId: number) {
  const body = (drafts.value[documentId] || "").trim();
  if (!body) return;
  const form = new FormData();
  form.append("body", body);
  await api.post(`/safety-features/inspections/${documentId}/comments`, form, { headers: { "Content-Type": "multipart/form-data" } });
  drafts.value[documentId] = "";
  await load();
}
onMounted(load);
</script>

