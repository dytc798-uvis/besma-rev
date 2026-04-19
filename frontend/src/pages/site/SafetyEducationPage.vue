<template>
  <div class="card">
    <div class="header-row">
      <div class="card-title">안전 교육</div>
      <button class="secondary" @click="load">새로고침</button>
    </div>

    <div v-if="canManage" class="upload-row">
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
          <td class="action-cell">
            <a :href="resolveUrl(item.file_url)" target="_blank" rel="noopener">보기</a>
            <button v-if="canManage" type="button" class="link-danger" @click="openDelete(item)">삭제</button>
          </td>
        </tr>
        <tr v-if="items.length === 0"><td colspan="4" style="text-align:center;color:#64748b">교육 자료가 없습니다.</td></tr>
      </tbody>
    </table>

    <section v-if="deletionItems.length > 0 || loadedOnce" class="deletion-section">
      <h3 class="deletion-title">삭제 이력</h3>
      <p class="deletion-hint">잘못 올린 자료 등 삭제 시 누가 삭제했는지 기록됩니다. 삭제 시 본인 비밀번호가 필요합니다.</p>
      <table v-if="deletionItems.length > 0" class="basic-table deletion-table">
        <thead>
          <tr>
            <th>삭제 시각</th>
            <th>삭제자</th>
            <th>삭제자 ID</th>
            <th>삭제된 제목</th>
            <th>파일명</th>
            <th>원 업로드자</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in deletionItems" :key="d.id">
            <td>{{ formatDateTime(d.deleted_at) }}</td>
            <td>{{ d.deleted_by_name }}</td>
            <td>{{ d.deleted_by_login }}</td>
            <td>{{ d.title }}</td>
            <td>{{ d.file_name }}</td>
            <td>{{ d.uploaded_by_name || "—" }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted-inline">삭제 이력이 없습니다.</p>
    </section>

    <div v-if="deleteTarget" class="modal-backdrop" role="dialog" aria-modal="true" @click.self="closeDelete">
      <div class="modal-box">
        <h4 class="modal-title">교육 자료 삭제</h4>
        <p class="modal-text">
          <strong>{{ deleteTarget.title }}</strong> 자료를 삭제합니다. 되돌릴 수 없습니다.
        </p>
        <label class="pwd-label" for="edu-del-pwd">본인 비밀번호</label>
        <input
          id="edu-del-pwd"
          v-model="deletePassword"
          type="password"
          class="pwd-input"
          autocomplete="current-password"
          @keyup.enter="submitDelete"
        />
        <p v-if="deleteError" class="error-text">{{ deleteError }}</p>
        <div class="modal-actions">
          <button type="button" class="secondary" :disabled="deleting" @click="closeDelete">취소</button>
          <button type="button" class="danger" :disabled="deleting || !deletePassword.trim()" @click="submitDelete">
            {{ deleting ? "삭제 중…" : "삭제 실행" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import axios from "axios";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { formatDateTimeKst } from "@/utils/datetime";

const auth = useAuthStore();
const items = ref<any[]>([]);
const deletionItems = ref<any[]>([]);
const loadedOnce = ref(false);
const title = ref("");
const file = ref<File | null>(null);
const uploading = ref(false);

const deleteTarget = ref<{ id: number; title: string } | null>(null);
const deletePassword = ref("");
const deleteError = ref("");
const deleting = ref(false);

const canManage = computed(() =>
  ["HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN", "ACCIDENT_ADMIN"].includes(auth.user?.role ?? ""),
);

function formatDateTime(v?: string) {
  return formatDateTimeKst(v, "-");
}
function resolveUrl(path: string) {
  return `${api.defaults.baseURL}${path}`;
}
function onFileChange(e: Event) {
  file.value = (e.target as HTMLInputElement).files?.[0] ?? null;
}

async function load() {
  const [edu, del] = await Promise.all([
    api.get("/safety-features/education"),
    api.get("/safety-features/education/deletions"),
  ]);
  items.value = edu.data.items ?? [];
  deletionItems.value = del.data.items ?? [];
  loadedOnce.value = true;
}

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
  } finally {
    uploading.value = false;
  }
}

function openDelete(item: { id: number; title: string }) {
  deleteTarget.value = { id: item.id, title: item.title };
  deletePassword.value = "";
  deleteError.value = "";
}

function closeDelete() {
  if (deleting.value) return;
  deleteTarget.value = null;
  deletePassword.value = "";
  deleteError.value = "";
}

async function submitDelete() {
  if (!deleteTarget.value || !deletePassword.value.trim()) return;
  deleting.value = true;
  deleteError.value = "";
  try {
    await api.post(`/safety-features/education/${deleteTarget.value.id}/delete`, {
      password: deletePassword.value,
    });
    closeDelete();
    await load();
  } catch (e: unknown) {
    if (axios.isAxiosError(e) && e.response?.status === 403) {
      const d = e.response?.data;
      deleteError.value =
        typeof d === "object" && d && "detail" in d && typeof (d as { detail: unknown }).detail === "string"
          ? (d as { detail: string }).detail
          : "삭제할 수 없습니다.";
    } else {
      deleteError.value = "삭제 요청에 실패했습니다.";
    }
  } finally {
    deleting.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.upload-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 16px;
}
.action-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}
.link-danger {
  background: none;
  border: none;
  padding: 0;
  color: #b91c1c;
  font-size: 14px;
  cursor: pointer;
  text-decoration: underline;
}
.link-danger:hover {
  color: #991b1b;
}
.deletion-section {
  margin-top: 28px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}
.deletion-title {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
}
.deletion-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.45;
}
.deletion-table {
  margin-top: 8px;
}
.muted-inline {
  margin: 8px 0 0;
  font-size: 13px;
  color: #94a3b8;
}
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 16px;
}
.modal-box {
  width: 100%;
  max-width: 400px;
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
}
.modal-title {
  margin: 0 0 10px;
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
}
.modal-text {
  margin: 0 0 14px;
  font-size: 14px;
  color: #334155;
  line-height: 1.5;
}
.pwd-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 6px;
}
.pwd-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 15px;
}
.error-text {
  margin: 10px 0 0;
  font-size: 13px;
  color: #b91c1c;
  font-weight: 600;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
}
.danger {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid #dc2626;
  background: #dc2626;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}
.danger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
