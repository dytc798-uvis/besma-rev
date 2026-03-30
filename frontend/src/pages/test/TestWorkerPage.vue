<template>
  <div class="card">
    <div class="card-title">WORKER 테스트 허브</div>
    <label class="form-field">
      <span>access_token</span>
      <input v-model="accessToken" type="text" />
    </label>
    <label class="form-field" style="margin-top: 8px">
      <span>distribution_id</span>
      <input v-model.number="distributionId" type="text" />
    </label>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 8px">
      <label class="form-field">
        <span>lat</span>
        <input v-model.number="lat" type="text" />
      </label>
      <label class="form-field">
        <span>lng</span>
        <input v-model.number="lng" type="text" />
      </label>
    </div>
    <label class="form-field" style="margin-top: 8px">
      <span>end_status</span>
      <select v-model="endStatus">
        <option value="NORMAL">NORMAL</option>
        <option value="ISSUE">ISSUE</option>
      </select>
    </label>

    <div class="toolbar" style="margin-top: 12px">
      <div class="toolbar-actions">
        <button class="primary" @click="listMine">1) 내 배포 목록</button>
        <button class="primary" @click="detail">2) 상세(viewed_at)</button>
        <button class="primary" @click="signStart">3) sign-start</button>
        <button class="primary" @click="signEnd">4) sign-end</button>
      </div>
    </div>
    <pre style="margin-top: 12px; white-space: pre-wrap">{{ resultText }}</pre>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { api } from "@/services/api";

const accessToken = ref("");
const distributionId = ref<number | null>(null);
const lat = ref(37.12345);
const lng = ref(127.12345);
const endStatus = ref<"NORMAL" | "ISSUE">("NORMAL");
const resultText = ref("");

const signatureData = (() => {
  const fake = "\x89PNG\r\n\x1a\n" + "\x00".repeat(300);
  return "data:image/png;base64," + btoa(fake);
})();

function setResult(payload: unknown) {
  resultText.value = JSON.stringify(payload, null, 2);
}

async function listMine() {
  const res = await api.get("/worker/my-daily-work-plans", {
    params: { access_token: accessToken.value },
  });
  setResult(res.data);
}

async function detail() {
  if (!distributionId.value) return;
  const res = await api.get(`/worker/my-daily-work-plans/${distributionId.value}`, {
    params: { access_token: accessToken.value },
  });
  setResult(res.data);
}

async function signStart() {
  if (!distributionId.value) return;
  const res = await api.post(`/worker/my-daily-work-plans/${distributionId.value}/sign-start`, {
    access_token: accessToken.value,
    signature_data: signatureData,
    signature_mime: "image/png",
    lat: lat.value,
    lng: lng.value,
  });
  setResult(res.data);
}

async function signEnd() {
  if (!distributionId.value) return;
  const res = await api.post(`/worker/my-daily-work-plans/${distributionId.value}/sign-end`, {
    access_token: accessToken.value,
    end_status: endStatus.value,
    signature_data: signatureData,
    signature_mime: "image/png",
    lat: lat.value,
    lng: lng.value,
  });
  setResult(res.data);
}
</script>
