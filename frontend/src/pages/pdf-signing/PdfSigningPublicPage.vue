<template>
  <div class="sign-shell">
    <div class="sign-card">
      <h1>전자 서명</h1>
      <p v-if="fixedSlot" class="muted">임시 서명 페이지 · {{ fixedSlot }}</p>
      <p v-if="loading" class="muted">불러오는 중…</p>
      <p v-else-if="loadError" class="error">{{ loadError }}</p>
      <template v-else-if="info">
        <p class="intro">
          <strong>{{ info.signer_name }}</strong> ({{ info.signer_title }}) 님, 아래에 서명해 주세요.
        </p>
        <p v-if="info.purpose_label" class="muted">문서: {{ info.purpose_label }}</p>
        <p v-if="info.status !== 'pending'" class="error">
          {{ info.status === "signed" ? "이미 서명이 완료된 링크입니다." : "만료된 링크입니다." }}
        </p>
        <template v-else>
          <div class="canvas-wrap">
            <canvas
              ref="canvasEl"
              class="sig-canvas"
              width="560"
              height="180"
              @pointerdown="startDraw"
              @pointermove="draw"
              @pointerup="endDraw"
              @pointerleave="endDraw"
            />
          </div>
          <div class="actions">
            <button type="button" class="secondary" @click="clearCanvas">지우기</button>
            <button type="button" class="primary" :disabled="submitting" @click="submit">
              {{ submitting ? "저장 중…" : "서명 완료" }}
            </button>
          </div>
          <p v-if="submitError" class="error">{{ submitError }}</p>
          <p v-if="done" class="success">서명이 완료되었습니다. 창을 닫으셔도 됩니다.</p>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { api } from "@/services/api";

type PublicInfo = {
  signer_name: string;
  signer_title: string;
  purpose_label: string | null;
  original_filename: string;
  status: string;
  expires_at: string;
};

const props = defineProps<{
  fixedSlot?: "sign1" | "sign2";
}>();

const route = useRoute();
const token = String(route.params.token || "");
const info = ref<PublicInfo | null>(null);
const loading = ref(true);
const loadError = ref("");
const submitError = ref("");
const submitting = ref(false);
const done = ref(false);

const canvasEl = ref<HTMLCanvasElement | null>(null);
let drawing = false;
let hasInk = false;

function publicInfoPath() {
  if (props.fixedSlot) return `/pdf-signing/public/slot/${props.fixedSlot}`;
  return `/pdf-signing/public/${token}`;
}

function publicSignPath() {
  if (props.fixedSlot) return `/pdf-signing/public/slot/${props.fixedSlot}/sign`;
  return `/pdf-signing/public/${token}/sign`;
}

function getCtx() {
  const canvas = canvasEl.value;
  if (!canvas) return null;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.lineWidth = 2.2;
  ctx.lineCap = "round";
  ctx.strokeStyle = "#111827";
  return ctx;
}

function startDraw(e: PointerEvent) {
  const ctx = getCtx();
  const canvas = canvasEl.value;
  if (!ctx || !canvas) return;
  drawing = true;
  canvas.setPointerCapture(e.pointerId);
  const rect = canvas.getBoundingClientRect();
  const x = ((e.clientX - rect.left) / rect.width) * canvas.width;
  const y = ((e.clientY - rect.top) / rect.height) * canvas.height;
  ctx.beginPath();
  ctx.moveTo(x, y);
}

function draw(e: PointerEvent) {
  if (!drawing) return;
  const ctx = getCtx();
  const canvas = canvasEl.value;
  if (!ctx || !canvas) return;
  const rect = canvas.getBoundingClientRect();
  const x = ((e.clientX - rect.left) / rect.width) * canvas.width;
  const y = ((e.clientY - rect.top) / rect.height) * canvas.height;
  ctx.lineTo(x, y);
  ctx.stroke();
  hasInk = true;
}

function endDraw(e: PointerEvent) {
  if (!drawing) return;
  drawing = false;
  canvasEl.value?.releasePointerCapture(e.pointerId);
}

function clearCanvas() {
  const canvas = canvasEl.value;
  const ctx = getCtx();
  if (!canvas || !ctx) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  hasInk = false;
}

async function loadInfo() {
  loading.value = true;
  loadError.value = "";
  try {
    const res = await api.get(publicInfoPath(), { skipAuthRedirect: true });
    info.value = res.data;
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    loadError.value =
      status === 404 && props.fixedSlot
        ? "아직 관리자가 PDF를 등록하지 않았습니다."
        : "유효하지 않거나 만료된 링크입니다.";
  } finally {
    loading.value = false;
  }
}

async function submit() {
  submitError.value = "";
  const canvas = canvasEl.value;
  if (!canvas || !hasInk) {
    submitError.value = "서명을 입력해 주세요.";
    return;
  }
  submitting.value = true;
  try {
    const signature_png_base64 = canvas.toDataURL("image/png");
    await api.post(publicSignPath(), { signature_png_base64 }, { skipAuthRedirect: true });
    done.value = true;
    if (info.value) info.value.status = "signed";
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    submitError.value = typeof detail === "string" ? detail : "서명 저장에 실패했습니다.";
  } finally {
    submitting.value = false;
  }
}

onMounted(() => {
  void loadInfo();
});
</script>

<style scoped>
.sign-shell {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
  padding: 16px;
}
.sign-card {
  width: min(640px, 100%);
  background: #fff;
  border-radius: 14px;
  padding: 20px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}
h1 { margin: 0 0 8px; font-size: 22px; }
.intro { margin: 0 0 8px; }
.muted { color: #64748b; font-size: 13px; }
.canvas-wrap { border: 1px dashed #94a3b8; border-radius: 10px; background: #fff; margin: 12px 0; }
.sig-canvas { width: 100%; height: 180px; touch-action: none; display: block; }
.actions { display: flex; gap: 8px; }
.primary, .secondary { padding: 10px 14px; border-radius: 8px; border: none; cursor: pointer; }
.primary { background: #2563eb; color: #fff; }
.secondary { background: #e2e8f0; }
.error { color: #dc2626; }
.success { color: #15803d; }
</style>
