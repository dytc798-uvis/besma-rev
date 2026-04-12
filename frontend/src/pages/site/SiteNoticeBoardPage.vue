<template>
  <div class="notice-page">
    <BaseCard title="공지사항">
      <template #actions>
        <button class="secondary" @click="loadNotices">새로고침</button>
      </template>

      <div class="notice-layout">
        <aside class="notice-list">
          <button
            v-for="item in notices"
            :key="item.id"
            class="notice-item"
            :class="{ active: selectedNoticeId === item.id }"
            @click="selectNotice(item.id)"
          >
            <strong>{{ item.title }}</strong>
            <span>{{ formatDateTime(item.created_at) }}</span>
          </button>
          <p v-if="notices.length === 0" class="empty-text">공지사항이 없습니다.</p>
        </aside>

        <section class="notice-detail" v-if="selectedNotice">
          <div class="detail-head">
            <h3>{{ selectedNotice.title }}</h3>
            <button
              v-if="canDeleteSelectedNotice"
              class="secondary danger"
              :disabled="deletingNotice"
              @click="deleteSelectedNotice"
            >
              {{ deletingNotice ? "삭제 중..." : "공지 삭제" }}
            </button>
          </div>
          <p class="meta">
            작성자: {{ selectedNotice.created_by_name || "-" }} · {{ formatDateTime(selectedNotice.created_at) }}
          </p>
          <p class="body">{{ selectedNotice.body }}</p>

          <div class="comment-section">
            <h4>댓글</h4>
            <div class="comment-list">
              <article v-for="comment in comments" :key="comment.id" class="comment-item">
                <p>{{ comment.body }}</p>
                <span>{{ comment.created_by_name || "-" }} · {{ formatDateTime(comment.created_at) }}</span>
              </article>
              <p v-if="comments.length === 0" class="empty-text">댓글이 없습니다.</p>
            </div>

            <div class="comment-write">
              <textarea v-model="commentBody" rows="3" placeholder="댓글을 입력하세요." />
              <button class="primary" :disabled="!commentBody.trim() || writingComment" @click="submitComment">
                {{ writingComment ? "등록 중..." : "댓글 등록" }}
              </button>
            </div>
          </div>
        </section>
      </div>

      <section v-if="canCreateNotice" class="notice-create">
        <h3>공지 등록</h3>
        <input v-model="newNoticeTitle" type="text" placeholder="제목" />
        <textarea v-model="newNoticeBody" rows="4" placeholder="공지 내용" />
        <button class="primary" :disabled="!newNoticeTitle.trim() || !newNoticeBody.trim() || creatingNotice" @click="createNotice">
          {{ creatingNotice ? "등록 중..." : "공지 등록" }}
        </button>
      </section>
      <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { BaseCard } from "@/components/product";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { formatDateTimeKst } from "@/utils/datetime";

interface NoticeItem {
  id: number;
  title: string;
  body: string;
  created_by_user_id: number;
  created_by_name?: string | null;
  created_at: string;
}

interface NoticeComment {
  id: number;
  body: string;
  created_by_name?: string | null;
  created_at: string;
}

const auth = useAuthStore();
const notices = ref<NoticeItem[]>([]);
const selectedNoticeId = ref<number | null>(null);
const comments = ref<NoticeComment[]>([]);
const commentBody = ref("");
const writingComment = ref(false);
const newNoticeTitle = ref("");
const newNoticeBody = ref("");
const creatingNotice = ref(false);
const deletingNotice = ref(false);
const errorMessage = ref("");

const selectedNotice = computed(() => notices.value.find((n) => n.id === selectedNoticeId.value) ?? null);
const canCreateNotice = computed(() => ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN", "SITE"].includes(auth.user?.role ?? ""));
const canDeleteSelectedNotice = computed(() => {
  const notice = selectedNotice.value;
  if (!notice) return false;
  const role = auth.user?.role ?? "";
  const isAdmin = role === "HQ_SAFE_ADMIN" || role === "SUPER_ADMIN";
  const isAuthor = Number(auth.user?.id ?? 0) === Number(notice.created_by_user_id);
  return isAdmin || isAuthor;
});

function formatDateTime(value: string | null | undefined) {
  return formatDateTimeKst(value, "-");
}

async function loadNotices() {
  errorMessage.value = "";
  try {
    const res = await api.get("/notices");
    notices.value = res.data.items ?? [];
    if (!selectedNoticeId.value && notices.value.length > 0) {
      selectedNoticeId.value = notices.value[0].id;
    }
    if (selectedNoticeId.value) {
      await loadNoticeDetail(selectedNoticeId.value);
    } else {
      comments.value = [];
    }
  } catch (error: unknown) {
    notices.value = [];
    comments.value = [];
    const statusCode = (error as { response?: { status?: number } })?.response?.status;
    errorMessage.value =
      statusCode === 404
        ? "공지사항 API가 서버에 배포되지 않았습니다. 백엔드 최신 배포가 필요합니다."
        : "공지사항을 불러오지 못했습니다.";
  }
}

async function loadNoticeDetail(id: number) {
  const res = await api.get(`/notices/${id}`);
  comments.value = res.data.comments ?? [];
}

async function selectNotice(id: number) {
  selectedNoticeId.value = id;
  await loadNoticeDetail(id);
}

async function submitComment() {
  if (!selectedNoticeId.value || !commentBody.value.trim()) return;
  writingComment.value = true;
  try {
    await api.post(`/notices/${selectedNoticeId.value}/comments`, { body: commentBody.value });
    commentBody.value = "";
    await loadNoticeDetail(selectedNoticeId.value);
  } finally {
    writingComment.value = false;
  }
}

async function createNotice() {
  if (!newNoticeTitle.value.trim() || !newNoticeBody.value.trim()) return;
  creatingNotice.value = true;
  errorMessage.value = "";
  try {
    await api.post("/notices", { title: newNoticeTitle.value, body: newNoticeBody.value });
    newNoticeTitle.value = "";
    newNoticeBody.value = "";
    await loadNotices();
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    errorMessage.value = detail || "공지 등록에 실패했습니다.";
  } finally {
    creatingNotice.value = false;
  }
}

async function deleteSelectedNotice() {
  if (!selectedNotice.value) return;
  if (!window.confirm("이 공지사항을 삭제하시겠습니까?")) return;
  deletingNotice.value = true;
  errorMessage.value = "";
  try {
    const deletingId = selectedNotice.value.id;
    await api.delete(`/notices/${deletingId}`);
    const nextItem = notices.value.find((item) => item.id !== deletingId) ?? null;
    selectedNoticeId.value = nextItem?.id ?? null;
    await loadNotices();
  } catch (error: unknown) {
    const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    errorMessage.value = detail || "공지 삭제에 실패했습니다.";
  } finally {
    deletingNotice.value = false;
  }
}

onMounted(loadNotices);
</script>

<style scoped>
.notice-layout { display: grid; grid-template-columns: 320px 1fr; gap: 12px; }
.notice-list { border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; max-height: 520px; overflow: auto; }
.notice-item { width: 100%; border: 1px solid #e5e7eb; background: #fff; border-radius: 8px; padding: 10px; margin-bottom: 8px; text-align: left; display: flex; flex-direction: column; gap: 4px; cursor: pointer; }
.notice-item.active { border-color: #2563eb; background: #eff6ff; }
.notice-item span { color: #64748b; font-size: 12px; }
.notice-detail { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
.detail-head { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.detail-head h3 { margin: 0; }
.danger { color: #b91c1c; }
.meta { color: #64748b; font-size: 12px; margin: 4px 0 8px; }
.body { white-space: pre-wrap; margin: 0 0 14px; }
.comment-section { border-top: 1px solid #e5e7eb; padding-top: 10px; }
.comment-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; }
.comment-item { border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px; }
.comment-item p { margin: 0 0 4px; white-space: pre-wrap; }
.comment-item span { color: #64748b; font-size: 12px; }
.comment-write { display: flex; flex-direction: column; gap: 8px; }
.notice-create { margin-top: 14px; border-top: 1px solid #e5e7eb; padding-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.empty-text { color: #64748b; font-size: 13px; }
.error-message { margin-top: 10px; color: #b91c1c; font-weight: 600; }
@media (max-width: 920px) { .notice-layout { grid-template-columns: 1fr; } }
</style>
