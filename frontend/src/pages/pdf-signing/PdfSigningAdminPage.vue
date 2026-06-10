<template>
  <div class="card">
    <div class="card-title">PDF 외부 서명 (임시)</div>
    <p class="muted">
      고정 URL 두 개로 운영합니다. 사고보고서 1페이지 상단 PM 칸에 서명이 삽입됩니다.
    </p>

    <section v-for="slot in slots" :key="slot.slot" class="slot-card">
      <div class="slot-head">
        <div>
          <strong>{{ slot.slot_label }}</strong>
          <p class="muted slot-url">{{ slot.sign_url }}</p>
        </div>
        <button type="button" class="secondary small" @click="copyLink(slot.sign_url)">링크 복사</button>
      </div>

      <p v-if="slot.request" class="slot-status">
        상태: {{ slot.request.status }}
        · {{ slot.request.signer_name }} ({{ slot.request.signer_title }})
        <span v-if="slot.request.signed_at"> · 서명 {{ formatDt(slot.request.signed_at) }}</span>
      </p>
      <p v-else class="muted">아직 PDF가 등록되지 않았습니다.</p>

      <form class="form-stack" @submit.prevent="createSlot(slot.slot)">
        <div class="form-grid">
          <div class="field">
            <label class="lbl">서명자 이름</label>
            <input v-model="forms[slot.slot].signer_name" class="input" required />
          </div>
          <div class="field">
            <label class="lbl">서명자 직급</label>
            <input v-model="forms[slot.slot].signer_title" class="input" required />
          </div>
          <div class="field">
            <label class="lbl">만료(시간)</label>
            <input v-model.number="forms[slot.slot].expires_hours" class="input" type="number" min="1" max="720" />
          </div>
        </div>
        <div class="field">
          <label class="lbl">PDF 파일</label>
          <input type="file" accept="application/pdf,.pdf" required @change="onFileChange(slot.slot, $event)" />
        </div>
        <button type="submit" class="primary" :disabled="creatingSlot === slot.slot">
          {{ creatingSlot === slot.slot ? "등록 중…" : `${slot.slot} PDF 등록` }}
        </button>
      </form>

      <div v-if="slot.request" class="actions">
        <button type="button" class="secondary small" @click="download(slot.request!.id, 'original')">원본</button>
        <button
          type="button"
          class="secondary small"
          :disabled="slot.request.status !== 'signed'"
          @click="download(slot.request!.id, 'signed')"
        >
          서명본
        </button>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { api } from "@/services/api";

type Row = {
  id: number;
  status: string;
  signer_name: string;
  signer_title: string;
  signed_at: string | null;
};

type SlotSummary = {
  slot: "sign1" | "sign2";
  slot_label: string;
  sign_url: string;
  request: Row | null;
};

const slots = ref<SlotSummary[]>([]);
const creatingSlot = ref<string | null>(null);
const error = ref("");
const selectedFiles = reactive<Record<string, File | null>>({
  sign1: null,
  sign2: null,
});

const forms = reactive({
  sign1: { signer_name: "최재필", signer_title: "전무", expires_hours: 168 },
  sign2: { signer_name: "테스트", signer_title: "관리자", expires_hours: 168 },
});

function onFileChange(slot: string, e: Event) {
  const input = e.target as HTMLInputElement;
  selectedFiles[slot] = input.files?.[0] ?? null;
}

function formatDt(v: string) {
  return new Date(v).toLocaleString("ko-KR");
}

async function loadSlots() {
  const res = await api.get("/pdf-signing/slots");
  slots.value = res.data;
}

async function createSlot(slot: string) {
  error.value = "";
  const file = selectedFiles[slot];
  if (!file) {
    error.value = "PDF 파일을 선택해 주세요.";
    return;
  }
  creatingSlot.value = slot;
  try {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("signer_name", forms[slot as "sign1" | "sign2"].signer_name.trim());
    fd.append("signer_title", forms[slot as "sign1" | "sign2"].signer_title.trim());
    fd.append("expires_hours", String(forms[slot as "sign1" | "sign2"].expires_hours));
    await api.post(`/pdf-signing/slots/${slot}`, fd);
    await loadSlots();
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof msg === "string" ? msg : "등록에 실패했습니다.";
  } finally {
    creatingSlot.value = null;
  }
}

async function copyLink(url: string) {
  await navigator.clipboard.writeText(url);
  alert("링크가 복사되었습니다.");
}

async function download(id: number, kind: "original" | "signed") {
  const res = await api.get(`/pdf-signing/requests/${id}/download`, {
    params: { kind },
    responseType: "blob",
  });
  const blob = new Blob([res.data], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = kind === "signed" ? `signed-${id}.pdf` : `original-${id}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

onMounted(() => {
  void loadSlots();
});
</script>

<style scoped>
.muted { color: #64748b; font-size: 13px; }
.form-stack { display: flex; flex-direction: column; gap: 12px; margin-top: 12px; }
.form-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.lbl { font-size: 13px; font-weight: 600; }
.input { padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 8px; }
.primary, .secondary { padding: 8px 14px; border-radius: 8px; border: none; cursor: pointer; }
.primary { background: #2563eb; color: #fff; }
.secondary { background: #e2e8f0; color: #0f172a; }
.small { padding: 4px 8px; font-size: 12px; }
.error { color: #dc2626; margin-top: 12px; }
.slot-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  background: #f8fafc;
}
.slot-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.slot-url { margin: 4px 0 0; font-family: ui-monospace, monospace; }
.slot-status { margin: 8px 0 0; font-size: 13px; }
.actions { display: flex; gap: 8px; margin-top: 10px; }
</style>
