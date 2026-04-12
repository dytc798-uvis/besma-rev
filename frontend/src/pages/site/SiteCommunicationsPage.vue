<template>
  <div class="card comm-page">
    <div class="header-row">
      <div>
        <div class="card-title">소통자료</div>
        <p class="helper">같은 현장 사용자끼리 공유된 사진 자료를 확인합니다.</p>
      </div>
      <button class="secondary" type="button" @click="loadList">새로고침</button>
    </div>

    <div class="layout-grid">
      <section class="list-panel">
        <div v-if="loading" class="empty">불러오는 중...</div>
        <div v-else-if="items.length === 0" class="empty">수신된 소통자료가 없습니다.</div>
        <button
          v-for="item in items"
          :key="item.id"
          type="button"
          class="list-item"
          :class="{ active: selected?.id === item.id, unread: !item.is_read }"
          @click="selectItem(item)"
        >
          <div class="title-row">
            <strong>{{ item.title || "(제목 없음)" }}</strong>
            <span v-if="!item.is_read" class="badge">미확인</span>
          </div>
          <div class="meta">
            {{ item.sender.name }} · {{ formatDate(item.created_at) }} · 사진 {{ item.attachments.length }}장
          </div>
        </button>
      </section>

      <section class="detail-panel">
        <div v-if="!selected" class="empty">좌측 목록에서 자료를 선택하세요.</div>
        <template v-else>
          <div class="detail-head">
            <h3>{{ selected.title || "(제목 없음)" }}</h3>
            <div class="detail-actions">
              <button
                v-if="selected.bundle_pdf_download_url"
                type="button"
                class="secondary"
                @click="downloadBundlePdf"
              >
                PDF 다운로드
              </button>
              <button type="button" class="primary" @click="markRead" :disabled="selected.is_read">
                {{ selected.is_read ? "확인 완료" : "확인" }}
              </button>
            </div>
          </div>
          <p class="meta">{{ selected.sender.name }} · {{ selected.sender.login_id }} · {{ formatDate(selected.created_at) }}</p>
          <p v-if="selected.description" class="desc">{{ selected.description }}</p>
          <p v-if="selected.bundle_pdf_download_url" class="bundle-note">여러 장 업로드본은 제출/보관용 PDF로도 내려받을 수 있습니다.</p>
          <div class="image-grid">
            <div v-for="att in selected.attachments" :key="att.id" class="image-card">
              <img :src="previewUrls[att.id] || ''" :alt="att.original_name" />
              <button type="button" class="secondary" @click="downloadAttachment(att)">다운로드</button>
            </div>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/services/api";

interface CommunicationAttachment {
  id: number;
  original_name: string;
  file_type: string;
  uploaded_at: string;
  download_url: string;
}

interface CommunicationItem {
  id: number;
  title: string | null;
  description: string | null;
  created_at: string;
  is_read: boolean;
  bundle_pdf_download_url: string | null;
  sender: { id: number; name: string; login_id: string };
  attachments: CommunicationAttachment[];
}

const loading = ref(false);
const items = ref<CommunicationItem[]>([]);
const selected = ref<CommunicationItem | null>(null);
const previewUrls = ref<Record<number, string>>({});

async function loadPreviews(item: CommunicationItem | null) {
  Object.values(previewUrls.value).forEach((url) => URL.revokeObjectURL(url));
  previewUrls.value = {};
  if (!item) return;
  const entries = await Promise.all(
    item.attachments.map(async (att) => {
      try {
        const res = await api.get(att.download_url, { responseType: "blob" });
        return [att.id, URL.createObjectURL(res.data)] as const;
      } catch {
        return [att.id, ""] as const;
      }
    }),
  );
  previewUrls.value = Object.fromEntries(entries);
}

function formatDate(value: string) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(
    d.getHours(),
  ).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

async function loadList() {
  loading.value = true;
  try {
    const res = await api.get("/communications");
    items.value = (res.data ?? []) as CommunicationItem[];
    if (selected.value) {
      selected.value = items.value.find((v) => v.id === selected.value?.id) ?? null;
      await loadPreviews(selected.value);
    }
  } finally {
    loading.value = false;
  }
}

function selectItem(item: CommunicationItem) {
  selected.value = item;
  void loadPreviews(item);
}

async function markRead() {
  if (!selected.value || selected.value.is_read) return;
  await api.post(`/communications/${selected.value.id}/read`);
  await loadList();
}

async function downloadAttachment(att: CommunicationAttachment) {
  const res = await api.get(att.download_url, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = att.original_name;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function downloadBundlePdf() {
  if (!selected.value?.bundle_pdf_download_url) return;
  const res = await api.get(selected.value.bundle_pdf_download_url, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `communication_${selected.value.id}.pdf`;
  anchor.click();
  URL.revokeObjectURL(url);
}

onMounted(loadList);
</script>

<style scoped>
.comm-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.helper {
  margin: 6px 0 0;
  color: #64748b;
}
.layout-grid {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 12px;
}
.list-panel,
.detail-panel {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  padding: 10px;
  min-height: 380px;
}
.list-item {
  width: 100%;
  text-align: left;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  padding: 10px;
  margin-bottom: 8px;
}
.list-item.active {
  border-color: #3b82f6;
}
.list-item.unread {
  background: #eff6ff;
}
.title-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.meta {
  margin-top: 6px;
  color: #64748b;
  font-size: 12px;
}
.badge {
  font-size: 11px;
  color: #1d4ed8;
  background: #dbeafe;
  border-radius: 999px;
  padding: 2px 8px;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.detail-actions {
  display: flex;
  gap: 8px;
}
.desc {
  margin: 10px 0;
  white-space: pre-wrap;
}
.bundle-note {
  margin: 6px 0 10px;
  color: #475569;
  font-size: 13px;
}
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}
.image-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px;
}
.image-card img {
  width: 100%;
  height: 140px;
  object-fit: cover;
  border-radius: 6px;
  display: block;
  margin-bottom: 8px;
}
.empty {
  color: #64748b;
}
@media (max-width: 920px) {
  .layout-grid {
    grid-template-columns: 1fr;
  }
}
</style>

