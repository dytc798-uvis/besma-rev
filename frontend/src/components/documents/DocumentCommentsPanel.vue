<template>
  <section v-if="ledgerBlocked" class="doc-comments doc-comments-ledger-blocked">
    <h3 class="doc-comments-title">{{ title }}</h3>
    <p class="doc-comments-sub">{{ ledgerBlockedMessage }}</p>
    <p class="doc-comments-muted">문서 단위 코멘트는 사용할 수 없습니다.</p>
  </section>
  <section v-else class="doc-comments">
    <div class="doc-comments-head">
      <div>
        <h3 class="doc-comments-title">{{ title }}</h3>
        <p class="doc-comments-sub">승인/반려와 별개로 SITE/HQ가 자유롭게 메모를 누적합니다.</p>
      </div>
      <span v-if="comments.length" class="doc-comments-count">{{ comments.length }}건</span>
    </div>

    <p v-if="loadError" class="doc-comments-error">{{ loadError }}</p>
    <p v-else-if="loading" class="doc-comments-muted">코멘트를 불러오는 중...</p>

    <div v-else class="doc-comments-list">
      <p v-if="deleteError" class="doc-comments-error doc-comments-delete-err">{{ deleteError }}</p>
      <article v-for="item in comments" :key="item.id" class="doc-comment-item">
        <div class="doc-comment-meta">
          <div class="doc-comment-meta-main">
            <strong>{{ item.user_name }}</strong>
            <span class="doc-comment-role" :class="item.user_role === 'SITE' ? 'role-site' : 'role-hq'">{{ item.user_role }}</span>
            <span>{{ formatDateTime(item.created_at) }}</span>
          </div>
          <button
            v-if="canDeleteComment(item)"
            type="button"
            class="secondary doc-comment-delete"
            :disabled="deletingId === item.id"
            @click="confirmDelete(item)"
          >
            {{ deletingId === item.id ? "삭제 중..." : "삭제" }}
          </button>
        </div>
        <p class="doc-comment-text">{{ item.comment_text }}</p>
      </article>
      <p v-if="comments.length === 0" class="doc-comments-muted">등록된 코멘트가 없습니다.</p>
    </div>

    <div class="doc-comment-form">
      <label class="doc-comment-label" for="doc-comment-textarea">코멘트</label>
      <textarea
        id="doc-comment-textarea"
        v-model="draft"
        class="doc-comment-textarea"
        rows="3"
        placeholder="현장/본사 공통 메모를 남기세요."
      />
      <p v-if="submitError" class="doc-comments-error">{{ submitError }}</p>
      <div class="doc-comment-actions">
        <button type="button" class="stitch-btn-primary" :disabled="submitting || !canSubmit" @click="submitComment">
          {{ submitting ? "등록 중..." : "코멘트 등록" }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { formatDateTimeKst } from "@/utils/datetime";
import { isLedgerManagedDocumentType, LEDGER_MANAGED_UX_MESSAGE } from "@/utils/ledgerManagedDocument";

interface DocumentCommentItem {
  id: number;
  document_id: number;
  instance_id: number | null;
  user_id: number;
  user_name: string;
  user_role: "SITE" | "HQ";
  comment_text: string;
  created_at: string;
}

const props = withDefaults(
  defineProps<{
    documentId: number | null;
    title?: string;
    /** 백엔드 `Document.document_type`과 동일. 있으면 관리대장 전용 문서에서 코멘트 UI를 열지 않는다. */
    documentTypeCode?: string | null;
  }>(),
  {
    title: "문서 코멘트",
  },
);

const ledgerBlocked = computed(() => isLedgerManagedDocumentType(props.documentTypeCode));
const ledgerBlockedMessage = LEDGER_MANAGED_UX_MESSAGE;

const comments = ref<DocumentCommentItem[]>([]);
const loading = ref(false);
const loadError = ref("");
const draft = ref("");
const submitting = ref(false);
const submitError = ref("");
const deletingId = ref<number | null>(null);
const deleteError = ref("");

const auth = useAuthStore();

const canSubmit = computed(() => Boolean(props.documentId && draft.value.trim()));

function canDeleteComment(item: DocumentCommentItem): boolean {
  const user = auth.user;
  if (!user) return false;
  if ((user.login_id || "").trim().toLowerCase() === "hq01") return true;
  return item.user_id === user.id;
}

function formatDateTime(value: string | null) {
  return formatDateTimeKst(value, "—");
}

async function loadComments() {
  if (ledgerBlocked.value) {
    comments.value = [];
    loadError.value = "";
    loading.value = false;
    return;
  }
  if (!props.documentId) {
    comments.value = [];
    loadError.value = "";
    loading.value = false;
    return;
  }
  loading.value = true;
  loadError.value = "";
  try {
    const res = await api.get<DocumentCommentItem[]>(`/documents/${props.documentId}/comments`);
    comments.value = res.data ?? [];
    deleteError.value = "";
  } catch {
    comments.value = [];
    loadError.value = "코멘트를 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
}

async function submitComment() {
  if (!props.documentId || !draft.value.trim()) return;
  submitting.value = true;
  submitError.value = "";
  try {
    await api.post(`/documents/${props.documentId}/comments`, {
      comment_text: draft.value.trim(),
    });
    draft.value = "";
    await loadComments();
  } catch {
    submitError.value = "코멘트 등록에 실패했습니다. 잠시 후 다시 시도해 주세요.";
  } finally {
    submitting.value = false;
  }
}

async function confirmDelete(item: DocumentCommentItem) {
  if (!props.documentId) return;
  if (!window.confirm("정말 삭제할까요?")) return;
  deletingId.value = item.id;
  deleteError.value = "";
  try {
    await api.delete(`/documents/${props.documentId}/comments/${item.id}`);
    await loadComments();
  } catch {
    deleteError.value = "코멘트를 삭제하지 못했습니다.";
  } finally {
    deletingId.value = null;
  }
}

watch(
  () => [props.documentId, props.documentTypeCode] as const,
  () => {
    draft.value = "";
    submitError.value = "";
    deleteError.value = "";
    void loadComments();
  },
  { immediate: true },
);
</script>

<style scoped>
.doc-comments {
  border-top: 1px solid #e2e8f0;
  margin-top: 18px;
  padding-top: 18px;
}

.doc-comments-ledger-blocked {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px 14px;
  margin-top: 18px;
  background: #f8fafc;
}

.doc-comments-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.doc-comments-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}

.doc-comments-sub,
.doc-comments-muted {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748b;
}

.doc-comments-count {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}

.doc-comments-list {
  margin-top: 14px;
  display: grid;
  gap: 10px;
}

.doc-comments-delete-err {
  margin: 0 0 4px;
}

.doc-comment-item {
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
}

.doc-comment-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #475569;
}

.doc-comment-meta-main {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  min-width: 0;
}

.doc-comment-delete {
  flex-shrink: 0;
  padding: 4px 10px;
  font-size: 12px;
}

.doc-comment-role {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 700;
}

.role-site {
  background: #dcfce7;
  color: #166534;
}

.role-hq {
  background: #dbeafe;
  color: #1d4ed8;
}

.doc-comment-text {
  margin: 8px 0 0;
  white-space: pre-wrap;
  color: #0f172a;
  font-size: 14px;
  line-height: 1.5;
}

.doc-comment-form {
  margin-top: 16px;
}

.doc-comment-label {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 700;
  color: #475569;
}

.doc-comment-textarea {
  width: 100%;
  min-height: 88px;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  resize: vertical;
  font-size: 14px;
}

.doc-comment-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

.doc-comments-error {
  margin: 10px 0 0;
  color: #b91c1c;
  font-size: 13px;
}
</style>
