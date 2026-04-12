<template>
  <div class="card">
    <div class="header-row">
      <div class="card-title">근로자의견청취</div>
      <button class="secondary" @click="load">새로고침</button>
    </div>
    <div class="upload-row">
      <input ref="ledgerFileInput" type="file" accept=".xlsx,.xls,.csv" @change="onFileChange" />
      <button class="primary" :disabled="!ledgerFile || uploading" @click="uploadLedger">
        {{ uploading ? "업로드 중..." : "대장 업로드" }}
      </button>
    </div>

    <table class="basic-table">
      <thead>
        <tr>
          <th>대장</th>
          <th>근로자</th>
          <th>생년월일</th>
          <th>휴대전화</th>
          <th>의견종류</th>
          <th>의견</th>
          <th>상태</th>
          <th>소통</th>
          <th>액션</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="item in items" :key="item.id">
          <tr>
            <td>{{ item.ledger_title }}</td>
            <td>{{ item.worker_name || "-" }}</td>
            <td>{{ item.worker_birth_date || "-" }}</td>
            <td>{{ item.worker_phone_number || "-" }}</td>
            <td>{{ item.opinion_kind || "-" }}</td>
            <td>{{ item.opinion_text }}</td>
            <td>
              <span class="badge" :class="{ ok: item.reward_candidate }">
                {{ statusText(item) }}
              </span>
            </td>
            <td>
              <button class="secondary" @click="toggleComments(item.id)">댓글</button>
            </td>
            <td class="actions">
              <button class="secondary" :disabled="!canSiteApprove(item)" @click="siteApprove(item.id)">현장승인</button>
              <button class="secondary" :disabled="!canHqCheck(item)" @click="hqCheck(item.id)">본사체크</button>
              <button class="primary" :disabled="!canPromote(item)" @click="promote(item.id)">포상후보</button>
            </td>
          </tr>
          <tr v-if="openedCommentsItemId === item.id">
            <td colspan="9">
              <div class="comment-list">
                <p v-for="c in item.comments" :key="c.id">- {{ c.body }} ({{ c.created_by_name || "-" }})</p>
                <p v-if="item.comments.length === 0" style="color:#64748b">댓글이 없습니다.</p>
              </div>
              <div class="comment-write">
                <input v-model="commentDrafts[item.id]" type="text" placeholder="댓글 입력" />
                <button class="secondary" @click="addComment(item.id)">등록</button>
              </div>
            </td>
          </tr>
        </template>
        <tr v-if="items.length === 0"><td colspan="9" style="text-align:center;color:#64748b">데이터가 없습니다.</td></tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const items = ref<any[]>([]);
const ledgerFile = ref<File | null>(null);
const ledgerFileInput = ref<HTMLInputElement | null>(null);
const uploading = ref(false);
const openedCommentsItemId = ref<number | null>(null);
const commentDrafts = ref<Record<number, string>>({});

const role = computed(() => auth.user?.role ?? "");

function onFileChange(e: Event) { ledgerFile.value = (e.target as HTMLInputElement).files?.[0] ?? null; }
function toggleComments(itemId: number) { openedCommentsItemId.value = openedCommentsItemId.value === itemId ? null : itemId; }
function statusText(item: any) {
  if (item.reward_candidate) return "포상후보";
  if (item.hq_checked) return "본사확인";
  if (item.site_approved) return "현장승인";
  return "등록";
}
function canSiteApprove(item: any) { return role.value === "SITE" && !item.site_approved; }
function canHqCheck(item: any) { return ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(role.value) && item.site_approved && !item.hq_checked; }
function canPromote(item: any) { return ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(role.value) && item.site_approved && item.hq_checked && !item.reward_candidate; }

async function load() { const res = await api.get("/safety-features/worker-voice/items"); items.value = res.data.items ?? []; }
async function uploadLedger() {
  if (!ledgerFile.value) return;
  uploading.value = true;
  try {
    const form = new FormData();
    form.append("file", ledgerFile.value);
    await api.post("/safety-features/worker-voice/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
    ledgerFile.value = null;
    if (ledgerFileInput.value) {
      ledgerFileInput.value.value = "";
    }
    await load();
  } finally { uploading.value = false; }
}
async function siteApprove(itemId: number) { await api.post(`/safety-features/worker-voice/items/${itemId}/site-approve`); await load(); }
async function hqCheck(itemId: number) { await api.post(`/safety-features/worker-voice/items/${itemId}/hq-check`); await load(); }
async function promote(itemId: number) { await api.post(`/safety-features/worker-voice/items/${itemId}/reward-candidate`); await load(); }
async function addComment(itemId: number) {
  const body = (commentDrafts.value[itemId] || "").trim();
  if (!body) return;
  const form = new FormData();
  form.append("body", body);
  await api.post(`/safety-features/worker-voice/items/${itemId}/comments`, form, { headers: { "Content-Type": "multipart/form-data" } });
  commentDrafts.value[itemId] = "";
  await load();
}
void load();
</script>

