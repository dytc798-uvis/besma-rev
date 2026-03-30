<template>
  <div class="card">
    <div class="card-title">기타 문서 / 참고자료 업로드</div>
    <p class="upload-page-desc">
      이 화면은 requirement 기반 문서취합 메인 흐름이 아닌, 참고자료/기타 문서 등록용입니다.
      문서취합 제출은 <strong>현장 문서취합(Requirement 리스트)</strong>에서 진행하세요.
    </p>
    <form class="form-grid" @submit.prevent="handleSubmit">
      <div class="form-field">
        <label>제목</label>
        <input v-model="title" type="text" required />
      </div>
      <div class="form-field">
        <label>문서 종류 (기타/참고자료)</label>
        <select v-model="documentType" required>
          <option value="ETC">기타</option>
          <option value="OPINION_RELATED">참고자료(의견 관련)</option>
        </select>
      </div>
      <div class="form-field" style="grid-column: span 2">
        <label>설명</label>
        <textarea v-model="description" rows="3" />
      </div>
      <div class="form-field" style="grid-column: span 2">
        <label>파일 업로드</label>
        <input type="file" @change="onFileChange" />
      </div>
      <div style="grid-column: span 2; display: flex; justify-content: flex-end; gap: 8px">
        <button type="button" class="secondary" @click="handleSaveDraft" :disabled="loading">
          임시저장
        </button>
        <button type="submit" class="primary" :disabled="loading">
          {{ loading ? "제출 중..." : "등록 및 제출" }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";

const title = ref("");
const documentType = ref("ETC");
const description = ref("");
const file = ref<File | null>(null);
const loading = ref(false);

const router = useRouter();

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    file.value = target.files[0];
  } else {
    file.value = null;
  }
}

async function createDocument(submitAfterCreate: boolean) {
  loading.value = true;
  try {
    const form = new FormData();
    form.append("title", title.value);
    form.append("document_type", documentType.value);
    form.append("site_id", "");
    form.append("description", description.value);
    if (file.value) {
      form.append("file", file.value);
    }
    const res = await api.post("/documents", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    const id = res.data.id;
    if (submitAfterCreate) {
      await api.post(`/documents/${id}/submit`, { comment: "초기 제출" });
    }
    router.push({ name: "site-document-detail", params: { id } });
  } finally {
    loading.value = false;
  }
}

async function handleSubmit() {
  await createDocument(true);
}

async function handleSaveDraft() {
  await createDocument(false);
}
</script>

<style scoped>
.upload-page-desc {
  margin: 6px 0 14px;
  font-size: 12px;
  color: #475569;
  line-height: 1.45;
}
</style>

