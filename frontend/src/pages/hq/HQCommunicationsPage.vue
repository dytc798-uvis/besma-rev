<template>
  <div class="card comm-page">
    <div class="header-row">
      <div>
        <div class="card-title">본사-현장 소통</div>
        <p class="helper">현장에서 남긴 문서 코멘트/승인 의견을 시간순으로 확인합니다.</p>
      </div>
      <div class="actions">
        <label class="check-row">
          <input v-model="showUnreadOnly" type="checkbox" />
          <span>미확인만</span>
        </label>
        <button type="button" class="secondary" @click="loadItems">새로고침</button>
      </div>
    </div>

    <div v-if="loading" class="empty">불러오는 중...</div>
    <div v-else-if="displayed.length === 0" class="empty">표시할 소통 항목이 없습니다.</div>
    <table v-else class="table">
      <thead>
        <tr>
          <th>시각</th>
          <th>현장</th>
          <th>작성자</th>
          <th>구분</th>
          <th>내용</th>
          <th>문서</th>
          <th>확인</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in displayed" :key="row.item_key" :class="{ unread: !isRead(row.item_key) }">
          <td>{{ formatDate(row.created_at) }}</td>
          <td>{{ row.site_name }}</td>
          <td>{{ row.user_name }}</td>
          <td>{{ row.source === "approval" ? "결재의견" : "코멘트" }}</td>
          <td class="comment">{{ row.comment_text || "-" }}</td>
          <td>
            <button type="button" class="secondary" @click="goDetail(row.document_id)">문서보기</button>
          </td>
          <td>
            <button
              type="button"
              class="secondary"
              :disabled="isRead(row.item_key)"
              @click="confirmRead(row.item_key)"
            >
              {{ isRead(row.item_key) ? "확인됨" : "확인" }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";

interface CommunicationItemRow {
  item_key: string;
  source: "comment" | "approval";
  document_id: number;
  site_name: string;
  user_name: string;
  comment_text: string | null;
  created_at: string;
  is_read: boolean;
}

const router = useRouter();
const loading = ref(false);
const showUnreadOnly = ref(true);
const rows = ref<CommunicationItemRow[]>([]);
const displayed = computed(() =>
  showUnreadOnly.value ? rows.value.filter((row) => !row.is_read) : rows.value,
);

function formatDate(value: string) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(
    d.getHours(),
  ).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function isRead(itemKey: string) {
  return rows.value.find((row) => row.item_key === itemKey)?.is_read ?? false;
}

async function confirmRead(itemKey: string) {
  await api.post("/documents/hq-communications/read", { item_keys: [itemKey] });
  rows.value = rows.value.map((row) => (row.item_key === itemKey ? { ...row, is_read: true } : row));
  window.dispatchEvent(new CustomEvent("besma-hq-communication-read", { detail: { itemKey } }));
}

function goDetail(documentId: number) {
  void router.push({ name: "hq-safe-document-detail", params: { id: String(documentId) } });
}

async function loadItems() {
  loading.value = true;
  try {
    const res = await api.get("/documents/hq-communications", { params: { limit: 120 } });
    rows.value = (res.data?.items ?? []) as CommunicationItemRow[];
  } finally {
    loading.value = false;
  }
}

onMounted(loadItems);
</script>

<style scoped>
.comm-page {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.helper {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.check-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #334155;
}
.table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
}
.table th,
.table td {
  border: 1px solid #e2e8f0;
  padding: 8px;
  font-size: 13px;
  text-align: left;
  vertical-align: top;
}
.table thead th {
  background: #f8fafc;
  font-weight: 700;
}
.table tr.unread {
  background: #eff6ff;
}
.comment {
  white-space: pre-wrap;
}
.empty {
  color: #64748b;
}
</style>
