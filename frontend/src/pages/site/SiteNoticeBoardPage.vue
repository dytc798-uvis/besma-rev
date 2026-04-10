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
          <h3>{{ selectedNotice.title }}</h3>
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
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { BaseCard } from "@/components/product";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

interface NoticeItem {
  id: number;
  title: string;
  body: string;
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

const selectedNotice = computed(() => notices.value.find((n) => n.id === selectedNoticeId.value) ?? null);
const canCreateNotice = computed(() => ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(auth.user?.role ?? ""));

function formatDateTime(value: string | null | undefined) {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(dt);
}

async function loadNotices() {
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
  try {
    await api.post("/notices", { title: newNoticeTitle.value, body: newNoticeBody.value });
    newNoticeTitle.value = "";
    newNoticeBody.value = "";
    await loadNotices();
  } finally {
    creatingNotice.value = false;
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
@media (max-width: 920px) { .notice-layout { grid-template-columns: 1fr; } }
</style>
