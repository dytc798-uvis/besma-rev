<template>
  <div class="sign-shell">
    <div class="sign-card" :class="{ 'sign-card--wide': phase === 'review' }">
      <h1>전자 서명</h1>
      <p v-if="fixedSlot" class="muted">임시 서명 페이지 · {{ fixedSlot }}</p>
      <p v-if="loading" class="muted">불러오는 중…</p>
      <p v-else-if="loadError" class="error">{{ loadError }}</p>
      <template v-else-if="info">
        <p class="intro">
          <strong>{{ info.signer_name }}</strong> ({{ info.signer_title }}) 님,
          <template v-if="phase === 'review'">문서를 끝까지 확인한 뒤 서명해 주세요.</template>
          <template v-else>아래에 서명해 주세요.</template>
        </p>
        <p v-if="info.purpose_label" class="muted">문서: {{ info.purpose_label }}</p>
        <p v-if="info.status !== 'pending'" class="error">
          {{ info.status === "signed" ? "이미 서명이 완료된 링크입니다." : "만료된 링크입니다." }}
        </p>
        <template v-else-if="!done">
          <template v-if="phase === 'review'">
            <p v-if="pdfLoading" class="muted">문서 불러오는 중…</p>
            <p v-else-if="pdfError" class="error">{{ pdfError }}</p>
            <template v-else>
              <div ref="pdfScrollEl" class="pdf-review" @scroll="onPdfScroll">
                <img
                  v-for="(src, idx) in pageImages"
                  :key="idx"
                  :src="src"
                  class="pdf-page-img"
                  :alt="`문서 ${idx + 1}페이지`"
                />
              </div>
              <p v-if="!scrolledToEnd" class="scroll-hint">문서 끝까지 내려 전체 내용을 확인해 주세요.</p>
              <p v-else class="scroll-hint scroll-hint--ok">문서 확인이 완료되었습니다.</p>
              <div class="actions">
                <button type="button" class="primary" :disabled="!scrolledToEnd" @click="goToSign">
                  서명하기
                </button>
              </div>
            </template>
          </template>
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
              <button type="button" class="secondary" @click="backToReview">문서 다시 보기</button>
              <button type="button" class="secondary" @click="clearCanvas">지우기</button>
              <button type="button" class="primary" :disabled="submitting" @click="submit">
                {{ submitting ? "저장 중…" : "서명 완료" }}
              </button>
            </div>
            <p v-if="submitError" class="error">{{ submitError }}</p>
          </template>
        </template>
        <p v-if="done" class="success">서명이 완료되었습니다. 창을 닫으셔도 됩니다.</p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { getDocument, GlobalWorkerOptions } from "pdfjs-dist";
import pdfjsWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { nextTick, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { api } from "@/services/api";

GlobalWorkerOptions.workerSrc = pdfjsWorker;

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

const phase = ref<"review" | "sign">("review");
const pdfLoading = ref(false);
const pdfError = ref("");
const pageImages = ref<string[]>([]);
const pdfScrollEl = ref<HTMLDivElement | null>(null);
const scrolledToEnd = ref(false);

const canvasEl = ref<HTMLCanvasElement | null>(null);
let drawing = false;
let hasInk = false;

function publicInfoPath() {
  if (props.fixedSlot) return `/pdf-signing/public/slot/${props.fixedSlot}`;
  return `/pdf-signing/public/${token}`;
}

function publicDocumentPath() {
  if (props.fixedSlot) return `/pdf-signing/public/slot/${props.fixedSlot}/document`;
  return `/pdf-signing/public/${token}/document`;
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

function onPdfScroll() {
  const el = pdfScrollEl.value;
  if (!el) return;
  scrolledToEnd.value = el.scrollTop + el.clientHeight >= el.scrollHeight - 32;
}

function checkScrollEnd() {
  const el = pdfScrollEl.value;
  if (!el) return;
  if (el.scrollHeight <= el.clientHeight + 32) {
    scrolledToEnd.value = true;
    return;
  }
  onPdfScroll();
}

async function loadPdfPreview() {
  pdfLoading.value = true;
  pdfError.value = "";
  pageImages.value = [];
  scrolledToEnd.value = false;
  try {
    const res = await api.get(publicDocumentPath(), {
      responseType: "blob",
      skipAuthRedirect: true,
    });
    const buf = await (res.data as Blob).arrayBuffer();
    const pdf = await getDocument({ data: buf }).promise;
    const images: string[] = [];
    for (let pageNum = 1; pageNum <= pdf.numPages; pageNum += 1) {
      const page = await pdf.getPage(pageNum);
      const viewport = page.getViewport({ scale: 1.35 });
      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("canvas");
      await page.render({ canvasContext: ctx, viewport }).promise;
      images.push(canvas.toDataURL("image/png"));
    }
    pageImages.value = images;
    await nextTick();
    checkScrollEnd();
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status;
    pdfError.value =
      status === 409
        ? "확인할 수 있는 문서가 없습니다."
        : "문서를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";
  } finally {
    pdfLoading.value = false;
  }
}

async function loadInfo() {
  loading.value = true;
  loadError.value = "";
  try {
    const res = await api.get(publicInfoPath(), { skipAuthRedirect: true });
    info.value = res.data;
    if (res.data.status === "pending") {
      await loadPdfPreview();
    }
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

function goToSign() {
  if (!scrolledToEnd.value) return;
  phase.value = "sign";
  submitError.value = "";
  void nextTick(() => clearCanvas());
}

function backToReview() {
  phase.value = "review";
  submitError.value = "";
  void nextTick(() => checkScrollEnd());
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
  align-items: flex-start;
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
.sign-card--wide {
  width: min(920px, 100%);
}
h1 {
  margin: 0 0 8px;
  font-size: 22px;
}
.intro {
  margin: 0 0 8px;
}
.muted {
  color: #64748b;
  font-size: 13px;
}
.pdf-review {
  max-height: min(70vh, 720px);
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  margin: 12px 0;
  padding: 8px;
}
.pdf-page-img {
  display: block;
  width: 100%;
  height: auto;
  margin: 0 auto 8px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.08);
}
.pdf-page-img:last-child {
  margin-bottom: 0;
}
.scroll-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #b45309;
}
.scroll-hint--ok {
  color: #15803d;
}
.canvas-wrap {
  border: 1px dashed #94a3b8;
  border-radius: 10px;
  background: #fff;
  margin: 12px 0;
}
.sig-canvas {
  width: 100%;
  height: 180px;
  touch-action: none;
  display: block;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.primary,
.secondary {
  padding: 10px 14px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
}
.primary:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.primary {
  background: #2563eb;
  color: #fff;
}
.secondary {
  background: #e2e8f0;
}
.error {
  color: #dc2626;
}
.success {
  color: #15803d;
}
</style>
