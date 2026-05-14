<template>
  <div class="card">
    <div class="card-title">HQ_ADMIN 테스트 허브</div>
    <p style="margin-top: 0; color: #6b7280; font-size: 13px">
      문서취합·문서 상세 진입을 빠르게 점검하는 테스트 전용 도구입니다.
    </p>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px">
      <label class="form-field">
        <span>document_id</span>
        <input v-model.number="documentId" type="text" />
      </label>
      <label class="form-field">
        <span>opinion_id</span>
        <input v-model.number="opinionId" type="text" />
      </label>
    </div>
    <div class="toolbar" style="margin-top: 10px">
      <div class="toolbar-actions">
        <button class="primary" @click="fetchTbmSummary">문서 요약 API 조회</button>
        <button class="primary" @click="goDocumentDetail">문서 상세 이동</button>
        <button class="primary" @click="goApprovalInbox">결재함 이동</button>
        <button class="primary" @click="goDocumentList">문서목록 이동</button>
      </div>
    </div>
    <pre style="margin-top: 12px; white-space: pre-wrap">{{ resultText }}</pre>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";

const documentId = ref<number | null>(null);
const opinionId = ref<number | null>(null);
const resultText = ref("");
const router = useRouter();

function setResult(payload: unknown) {
  resultText.value = JSON.stringify(payload, null, 2);
}

async function fetchTbmSummary() {
  if (!documentId.value) return;
  const res = await api.get(`/documents/${documentId.value}/tbm-summary`);
  setResult(res.data);
}

function goDocumentDetail() {
  if (!documentId.value) return;
  router.push({ name: "hq-safe-document-detail", params: { id: String(documentId.value) } });
}

function goApprovalInbox() {
  router.push({ name: "hq-safe-approval-inbox" });
}

function goDocumentList() {
  router.push({ name: "hq-safe-documents" });
}
</script>
