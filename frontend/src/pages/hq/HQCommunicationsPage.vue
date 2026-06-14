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
            <th>개선루프</th>
            <th>내용</th>
            <th>문서</th>
            <th>기한·담당</th>
            <th>확인</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in displayed" :key="row.item_key" :class="{ unread: !isRead(row.item_key) }">
            <td>{{ formatDate(row.created_at) }}</td>
            <td>{{ row.site_name }}</td>
            <td>{{ row.user_name }}</td>
            <td>{{ row.source === "approval" ? "결재의견" : "코멘트" }}</td>
            <td>
              <span class="loop-pill">{{ row.loop_status_label || loopLabel(row.loop_status) }}</span>
            </td>
            <td class="comment">{{ row.comment_text || "-" }}</td>
            <td>
              <button type="button" class="secondary" @click="goDetail(row.document_id)">문서보기</button>
            </td>
            <td class="patch-cell">
              <div v-if="row.instance_id != null" class="patch-stack">
                <input
                  v-model="patchDraft[row.item_key].due"
                  type="date"
                  class="patch-input"
                  :aria-label="`개선 기한 ${row.item_key}`"
                />
                <input
                  v-model.number="patchDraft[row.item_key].assignee"
                  type="number"
                  min="1"
                  class="patch-input patch-num"
                  placeholder="담당 user id"
                  :aria-label="`담당자 user id ${row.item_key}`"
                />
                <button type="button" class="secondary patch-save" @click="saveLoopPatch(row)">저장</button>
              </div>
              <span v-else class="subtle">—</span>
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
import { feedbackLoopLabelKo } from "@/utils/feedbackLoopLabels";
import { formatDateTimeKst } from "@/utils/datetime";

interface CommunicationItemRow {
  item_key: string;
  source: "comment" | "approval";
  document_id: number;
  instance_id: number | null;
  site_name: string;
  user_name: string;
  comment_text: string | null;
  created_at: string;
  is_read: boolean;
  loop_status: string;
  loop_status_label: string;
  improvement_due_date: string | null;
  assignee_user_id: number | null;
}

const router = useRouter();
const loading = ref(false);
const showUnreadOnly = ref(true);
const rows = ref<CommunicationItemRow[]>([]);
const patchDraft = ref<Record<string, { due: string; assignee: number | null }>>({});
const displayed = computed(() =>
  showUnreadOnly.value ? rows.value.filter((row) => !row.is_read) : rows.value,
);

function formatDate(value: string) {
  return formatDateTimeKst(value, value);
}

function isRead(itemKey: string) {
  return rows.value.find((row) => row.item_key === itemKey)?.is_read ?? false;
}

function loopLabel(status: string) {
  return feedbackLoopLabelKo(status);
}

function ensurePatchDraft(rowsIn: CommunicationItemRow[]) {
  const next: Record<string, { due: string; assignee: number | null }> = {};
  for (const row of rowsIn) {
    next[row.item_key] = {
      due: row.improvement_due_date ? row.improvement_due_date.slice(0, 10) : "",
      assignee: row.assignee_user_id,
    };
  }
  patchDraft.value = next;
}

async function saveLoopPatch(row: CommunicationItemRow) {
  if (row.instance_id == null) return;
  const draft = patchDraft.value[row.item_key] ?? { due: "", assignee: null };
  const body: { improvement_due_date?: string | null; assignee_user_id?: number | null } = {};
  if (draft.due) body.improvement_due_date = draft.due;
  else body.improvement_due_date = null;
  if (draft.assignee != null && Number.isFinite(draft.assignee)) body.assignee_user_id = draft.assignee;
  else body.assignee_user_id = null;
  await api.patch(`/documents/instances/${row.instance_id}/feedback-loop`, body);
  await loadItems();
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
    ensurePatchDraft(rows.value);
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
.loop-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f1f5f9;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}
.patch-cell {
  min-width: 168px;
}
.patch-stack {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.patch-input {
  width: 100%;
  font-size: 12px;
  padding: 4px 6px;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
}
.patch-num {
  max-width: 100%;
}
.patch-save {
  align-self: flex-start;
  font-size: 12px;
  padding: 4px 8px;
}
.subtle {
  color: #94a3b8;
  font-size: 12px;
}
</style>
