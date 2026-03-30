<template>
  <div class="signature-pad">
    <canvas
      ref="canvasRef"
      :width="width"
      :height="height"
      class="signature-canvas"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointerleave="onPointerUp"
      @pointercancel="onPointerUp"
    />
    <div class="signature-actions">
      <button class="secondary" type="button" @click="clear">서명 지우기</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

const props = withDefaults(
  defineProps<{
    width?: number;
    height?: number;
  }>(),
  {
    width: 560,
    height: 220,
  },
);

const canvasRef = ref<HTMLCanvasElement | null>(null);
const isDrawing = ref(false);

function getContext() {
  const canvas = canvasRef.value;
  if (!canvas) return null;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  return { canvas, ctx };
}

function setupCanvas() {
  const payload = getContext();
  if (!payload) return;
  const { canvas, ctx } = payload;
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.lineWidth = 3;
  ctx.strokeStyle = "#111827";
}

function getOffset(e: PointerEvent) {
  const canvas = canvasRef.value;
  if (!canvas) return { x: 0, y: 0 };
  const rect = canvas.getBoundingClientRect();
  return {
    x: ((e.clientX - rect.left) / rect.width) * canvas.width,
    y: ((e.clientY - rect.top) / rect.height) * canvas.height,
  };
}

function onPointerDown(e: PointerEvent) {
  const payload = getContext();
  if (!payload) return;
  isDrawing.value = true;
  payload.canvas.setPointerCapture(e.pointerId);
  const { x, y } = getOffset(e);
  payload.ctx.beginPath();
  payload.ctx.moveTo(x, y);
}

function onPointerMove(e: PointerEvent) {
  if (!isDrawing.value) return;
  const payload = getContext();
  if (!payload) return;
  const { x, y } = getOffset(e);
  payload.ctx.lineTo(x, y);
  payload.ctx.stroke();
}

function onPointerUp(e: PointerEvent) {
  const payload = getContext();
  if (!payload) return;
  isDrawing.value = false;
  if (payload.canvas.hasPointerCapture(e.pointerId)) {
    payload.canvas.releasePointerCapture(e.pointerId);
  }
  payload.ctx.closePath();
}

function clear() {
  setupCanvas();
}

function toDataUrl() {
  const canvas = canvasRef.value;
  if (!canvas) return "";
  return canvas.toDataURL("image/png");
}

onMounted(setupCanvas);

defineExpose({
  clear,
  toDataUrl,
});
</script>

<style scoped>
.signature-pad {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.signature-canvas {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  touch-action: none;
}

.signature-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
