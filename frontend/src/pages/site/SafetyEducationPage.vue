<template>
  <div class="card">
    <div class="header-row">
      <div class="card-title">안전 교육</div>
      <button class="secondary" @click="load">새로고침</button>
    </div>

    <div v-if="canUpload" class="upload-row">
      <input v-model="title" type="text" placeholder="교육 자료 제목" />
      <input type="file" @change="onFileChange" />
      <button class="primary" :disabled="!title.trim() || !file || uploading" @click="upload">
        {{ uploading ? "업로드 중..." : "업로드" }}
      </button>
    </div>

    <table class="basic-table">
      <thead>
        <tr>
          <th>제목</th>
          <th>업로드시각</th>
          <th>작성자</th>
          <th>액션</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.id">
          <td>{{ item.title }}</td>
          <td>{{ formatDateTime(item.uploaded_at) }}</td>
          <td>{{ item.uploaded_by_name || "-" }}</td>
          <td><a :href="resolveUrl(item.file_url)" target="_blank" rel="noopener">보기</a></td>
        </tr>
        <tr v-if="items.length === 0"><td colspan="4" style="text-align:center;color:#64748b">교육 자료가 없습니다.</td></tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { formatDateTimeKst } from "@/utils/datetime";

const auth = useAuthStore();
const items = ref<any[]>([]);
const title = ref("");
const file = ref<File | null>(null);
const uploading = ref(false);
const canUpload = computed(() => ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"].includes(auth.user?.role ?? ""));

function formatDateTime(v?: string) {
  return formatDateTimeKst(v, "-");
}
function resolveUrl(path: string) { return `${api.defaults.baseURL}${path}`; }
function onFileChange(e: Event) { file.value = (e.target as HTMLInputElement).files?.[0] ?? null; }
async function load() { const res = await api.get("/safety-features/education"); items.value = res.data.items ?? []; }
async function upload() {
  if (!file.value || !title.value.trim()) return;
  uploading.value = true;
  try {
    const form = new FormData();
    form.append("title", title.value.trim());
    form.append("file", file.value);
    await api.post("/safety-features/education/upload", form, { headers: { "Content-Type": "multipart/form-data" } });
    title.value = "";
    file.value = null;
    await load();
  } finally { uploading.value = false; }
}
onMounted(load);
</script>

