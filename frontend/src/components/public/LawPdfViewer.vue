<template>
  <div class="law-pdf-viewer">
    <div class="pdf-tools" aria-label="PDF 보기 도구"><button type="button" :disabled="currentPage <= 1 || !total" @click="go(currentPage - 1)">이전</button><label><input aria-label="원문 페이지" type="number" min="1" :max="total || 1" :value="currentPage" @change="go(Number(($event.target as HTMLInputElement).value))" /> / {{ total || '…' }}쪽</label><button type="button" :disabled="currentPage >= total" @click="go(currentPage + 1)">다음</button><button type="button" @click="zoom = Math.max(.5, zoom - .25)">축소 −</button><button type="button" @click="zoom = Math.min(3, zoom + .25)">확대 +</button><button type="button" @click="rotation = (rotation + 90) % 360">회전 ↻</button></div>
    <p v-if="error" role="alert">{{ error }} <a :href="url" target="_blank" rel="noopener">PDF 직접 열기</a></p><p v-else-if="loading" role="status">원문을 불러오는 중입니다.</p>
    <div ref="container" class="pdf-canvas-container" :aria-busy="loading"><canvas ref="canvas" :aria-label="`서명본 원문 ${currentPage}쪽`" role="img" /></div>
  </div>
</template>
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy, type RenderTask } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
GlobalWorkerOptions.workerSrc = workerUrl;
const props = defineProps<{ url: string; page: number }>();
const emit = defineEmits<{ page: [page: number] }>();
const currentPage = ref(props.page);
const total = ref(0);
const zoom = ref(1);
const rotation = ref(0);
const canvas = ref<HTMLCanvasElement | null>(null);
const container = ref<HTMLDivElement | null>(null);
const error = ref('');
const loading = ref(true);
let document: PDFDocumentProxy | null = null;
let renderTask: RenderTask | null = null;
let generation = 0;
let disposed = false;
let observer: ResizeObserver | null = null;
let resizeTimer: ReturnType<typeof setTimeout> | undefined;
const task = getDocument({ url: props.url, isEvalSupported: false });
function go(value: number) { if (!Number.isFinite(value) || !total.value) return; currentPage.value = Math.min(total.value, Math.max(1, Math.round(value))); emit('page', currentPage.value); }
async function render() {
  const run = ++generation;
  if (!document || !canvas.value || !container.value || disposed) return;
  loading.value = true;
  error.value = '';
  const previous = renderTask;
  previous?.cancel();
  try {
    if (previous) await previous.promise.catch(() => undefined);
    const page = await document.getPage(currentPage.value);
    if (run !== generation || disposed) return;
    const angle = (page.rotate + rotation.value) % 360;
    const natural = page.getViewport({ scale: 1, rotation: angle });
    const width = Math.max(200, container.value.clientWidth - 24);
    const scale = width / natural.width * zoom.value;
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    const viewport = page.getViewport({ scale: scale * pixelRatio, rotation: angle });
    canvas.value.width = Math.ceil(viewport.width);
    canvas.value.height = Math.ceil(viewport.height);
    canvas.value.style.width = `${viewport.width / pixelRatio}px`;
    canvas.value.style.height = `${viewport.height / pixelRatio}px`;
    renderTask = page.render({ canvasContext: canvas.value.getContext('2d')!, viewport });
    await renderTask.promise;
  } catch (e) { if (run === generation && !disposed && (e as Error).name !== 'RenderingCancelledException') error.value = '원문을 표시하지 못했습니다.'; }
  finally { if (run === generation && !disposed) loading.value = false; }
}
watch(() => props.page, go);
watch([currentPage, zoom, rotation], render);
onMounted(async () => {
  try { document = await task.promise; if (disposed) return; total.value = document.numPages; go(props.page); await render(); observer = new ResizeObserver(() => { clearTimeout(resizeTimer); resizeTimer = setTimeout(render, 150); }); if (container.value) observer.observe(container.value); }
  catch { if (!disposed) { loading.value = false; error.value = 'PDF를 불러오지 못했습니다.'; } }
});
onBeforeUnmount(() => { disposed = true; generation++; observer?.disconnect(); clearTimeout(resizeTimer); renderTask?.cancel(); void task.destroy(); });
</script>
<style scoped>
.pdf-tools { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding-bottom: 14px; }.pdf-tools button { border: 1px solid #cedeea; background: white; border-radius: 7px; color: #355a78; padding: 9px 12px; font-size: 12px; }.pdf-tools button:disabled { opacity: .45; }.pdf-tools label { color: #4b637b; font-size: 12px; }.pdf-tools input { width: 58px; padding: 7px; border: 1px solid #cedeea; background: white; border-radius: 5px; }.pdf-canvas-container { overflow: auto; background: #e4eaf0; border-radius: 10px; padding: 12px; min-height: 220px; }canvas { display: block; margin: auto; box-shadow: 0 2px 10px #0002; }.law-pdf-viewer > p { color: #526b84; font-size: 13px; }
</style>
