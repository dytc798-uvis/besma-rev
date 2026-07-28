<template>
  <section class="coupang-page">
    <header class="hero">
      <div>
        <p class="eyebrow">COUPANG SITE MVP</p>
        <h2>쿠팡 도면 작업계획</h2>
        <p>도면 위에 작업 아이콘과 현장사진을 배치하고 서버에 저장합니다.</p>
      </div>
      <span class="save-state" :class="{ saved: !dirty && currentId }">
        {{ saving ? "저장 중" : dirty ? "저장 필요" : currentId ? "저장됨" : "새 문서" }}
      </span>
    </header>

    <div v-if="loading" class="state-card">쿠팡 현장 정보를 확인하고 있습니다.</div>
    <div v-else-if="accessError" class="state-card error">{{ accessError }}</div>
    <template v-else>
      <nav class="mobile-tabs" aria-label="편집 단계">
        <button v-for="item in tabs" :key="item.key" type="button" :class="{ active: activeTab === item.key }" @click="activeTab = item.key">
          {{ item.label }}
        </button>
      </nav>

      <div class="workspace">
        <aside class="form-panel" :class="{ 'mobile-hidden': activeTab !== 'form' }">
          <div class="panel-title">
            <h3>작업 기본정보</h3>
            <button type="button" class="text-button" @click="newDocument">새로 작성</button>
          </div>
          <div class="field-grid">
            <label>작업일<input v-model="form.work_date" type="date" @input="markDirty" /></label>
            <label>층
              <select v-model="form.floor" @change="markDirty">
                <option>4F</option><option>6F</option><option>기타</option>
              </select>
            </label>
          </div>
          <label>문서 제목<input v-model="form.title" maxlength="160" @input="markDirty" /></label>
          <label>작업장소<input v-model="form.workplace" maxlength="200" @input="markDirty" /></label>
          <label>작업내용<textarea v-model="form.work_description" rows="3" @input="markDirty" /></label>
          <label>위험요인<textarea v-model="form.hazard" rows="3" @input="markDirty" /></label>
          <label>안전대책<textarea v-model="form.control" rows="3" @input="markDirty" /></label>
          <div class="field-grid">
            <label>협력업체<input v-model="form.contractor_name" maxlength="100" @input="markDirty" /></label>
            <label>관리감독자<input v-model="form.manager_name" maxlength="100" @input="markDirty" /></label>
          </div>
          <label>작업인원<input v-model.number="form.worker_count" type="number" min="0" max="9999" @input="markDirty" /></label>
          <label>비고<textarea v-model="form.notes" rows="2" @input="markDirty" /></label>
        </aside>

        <main class="drawing-panel" :class="{ 'mobile-hidden': activeTab !== 'drawing' }">
          <div class="panel-title drawing-heading">
            <div>
              <h3>도면 표시</h3>
              <p>아이콘 또는 사진을 추가한 뒤 손가락으로 위치를 옮기세요.</p>
            </div>
            <button type="button" class="text-button" @click="fitDrawing">전체 보기</button>
          </div>

          <div class="upload-row">
            <label class="upload-button">
              도면 배경 올리기
              <input type="file" accept="image/jpeg,image/png,image/webp" @change="uploadBackground" />
            </label>
            <label class="upload-button accent">
              현장사진 촬영·추가
              <input type="file" accept="image/*" capture="environment" @change="uploadPhoto" />
            </label>
          </div>

          <div class="tool-strip" aria-label="도면 아이콘">
            <button v-for="tool in iconTools" :key="tool.label" type="button" @click="addIcon(tool)">
              <span>{{ tool.glyph }}</span>{{ tool.label }}
            </button>
          </div>

          <div ref="canvasWrap" class="canvas-wrap">
            <svg
              ref="svgRef"
              class="drawing-svg"
              :viewBox="`0 0 ${drawing.width} ${drawing.height}`"
              role="img"
              aria-label="쿠팡 현장 작업 도면 편집기"
              @pointermove="moveObject"
              @pointerup="endDrag"
              @pointercancel="endDrag"
              @pointerleave="endDrag"
              @click.self="selectedId = null"
            >
              <rect width="100%" height="100%" fill="#f8fafc" />
              <image
                v-if="drawing.background_asset_id && assetUrls[drawing.background_asset_id]"
                :href="assetUrls[drawing.background_asset_id]"
                x="0" y="0" width="1600" height="1000"
                preserveAspectRatio="xMidYMid meet"
              />
              <g v-else class="empty-drawing">
                <rect x="40" y="40" width="1520" height="920" rx="24" fill="none" stroke="#cbd5e1" stroke-width="4" stroke-dasharray="18 14" />
                <text x="800" y="475" text-anchor="middle">도면 배경 이미지를 올려주세요</text>
                <text x="800" y="525" text-anchor="middle" class="small">JPG · PNG · WEBP, 최대 15MB</text>
              </g>

              <g
                v-for="object in drawing.objects"
                :key="object.id"
                :transform="`translate(${object.x} ${object.y})`"
                class="drawing-object"
                :class="{ selected: selectedId === object.id }"
                @pointerdown.stop.prevent="startDrag($event, object)"
                @click.stop="selectedId = object.id"
              >
                <template v-if="object.type === 'photo'">
                  <rect :width="object.w" :height="object.h" rx="12" fill="#fff" stroke="#fff" stroke-width="8" />
                  <image
                    v-if="object.asset_id && assetUrls[object.asset_id]"
                    :href="assetUrls[object.asset_id]"
                    :width="object.w" :height="object.h"
                    preserveAspectRatio="xMidYMid slice"
                  />
                  <rect :width="object.w" :height="object.h" rx="12" fill="none" stroke="#0f172a" stroke-width="4" />
                  <rect y="calc(100% - 38px)" :width="object.w" height="38" fill="#0f172a" opacity=".78" />
                  <text :x="object.w / 2" :y="object.h - 12" text-anchor="middle" fill="#fff" font-size="24">{{ object.label }}</text>
                </template>
                <template v-else>
                  <circle :cx="object.w / 2" :cy="object.h / 2" :r="object.w / 2 - 5" :fill="object.color" stroke="#fff" stroke-width="8" />
                  <text :x="object.w / 2" :y="object.h / 2 + 16" text-anchor="middle" font-size="48">{{ object.glyph }}</text>
                  <rect :x="-20" :y="object.h + 8" :width="object.w + 40" height="38" rx="10" fill="#0f172a" opacity=".88" />
                  <text :x="object.w / 2" :y="object.h + 35" text-anchor="middle" fill="#fff" font-size="24">{{ object.label }}</text>
                </template>
                <rect v-if="selectedId === object.id" x="-10" y="-10" :width="object.w + 20" :height="object.h + 65" rx="14" fill="none" stroke="#2563eb" stroke-width="6" stroke-dasharray="12 8" />
              </g>
            </svg>
          </div>

          <div v-if="selectedObject" class="selection-tools">
            <label>표시 이름<input v-model="selectedObject.label" maxlength="30" @input="markDirty" /></label>
            <label>크기
              <input v-model.number="selectedObject.w" type="range" min="70" max="480" @input="resizeSelected" />
            </label>
            <label v-if="selectedObject.type === 'icon'">색상<input v-model="selectedObject.color" type="color" @input="markDirty" /></label>
            <div class="selection-actions">
              <button type="button" @click="moveLayer(-1)">뒤로</button>
              <button type="button" @click="moveLayer(1)">앞으로</button>
              <button type="button" class="danger" @click="removeSelected">삭제</button>
            </div>
          </div>
        </main>

        <aside class="history-panel" :class="{ 'mobile-hidden': activeTab !== 'history' }">
          <div class="panel-title">
            <h3>저장 내역</h3>
            <button type="button" class="text-button" @click="loadDocuments">새로고침</button>
          </div>
          <p v-if="documents.length === 0" class="empty-list">저장된 작업계획이 없습니다.</p>
          <button v-for="doc in documents" :key="doc.id" type="button" class="history-item" :class="{ active: currentId === doc.id }" @click="openDocument(doc)">
            <strong>{{ doc.title }}</strong>
            <span>{{ doc.work_date }} · {{ doc.floor }} · 표시 {{ doc.drawing?.objects?.length || 0 }}개</span>
          </button>
        </aside>
      </div>

      <footer class="action-bar">
        <button type="button" class="secondary-action" @click="downloadPng">도면 PNG 저장</button>
        <button type="button" class="primary-action" :disabled="saving || uploading" @click="saveDocument">
          {{ uploading ? "사진 업로드 중" : saving ? "저장 중" : currentId ? "변경사항 저장" : "서버에 저장" }}
        </button>
      </footer>
      <p v-if="message" class="toast" :class="{ error: messageIsError }">{{ message }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "@/services/api";
import { todayKst } from "@/utils/datetime";

type TabKey = "form" | "drawing" | "history";
type DrawingObject = {
  id: string;
  type: "icon" | "photo";
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  color?: string;
  glyph?: string;
  asset_id?: string;
};
type Drawing = { width: number; height: number; background_asset_id: string | null; objects: DrawingObject[] };
type StoredDocument = Record<string, any> & { id: number; title: string; work_date: string; floor: string; drawing: Drawing };

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "form", label: "① 기본정보" },
  { key: "drawing", label: "② 도면·사진" },
  { key: "history", label: "③ 저장내역" },
];
const iconTools = [
  { label: "작업구역", glyph: "⚒", color: "#dc2626" },
  { label: "이동경로", glyph: "➜", color: "#2563eb" },
  { label: "소화기", glyph: "🧯", color: "#ef4444" },
  { label: "비상구", glyph: "↗", color: "#16a34a" },
  { label: "작업자", glyph: "👷", color: "#f59e0b" },
  { label: "고소작업", glyph: "▲", color: "#ea580c" },
  { label: "감전위험", glyph: "⚡", color: "#7c3aed" },
];

const loading = ref(true);
const saving = ref(false);
const uploading = ref(false);
const dirty = ref(false);
const accessError = ref("");
const message = ref("");
const messageIsError = ref(false);
const activeTab = ref<TabKey>("drawing");
const currentId = ref<number | null>(null);
const documents = ref<StoredDocument[]>([]);
const selectedId = ref<string | null>(null);
const svgRef = ref<SVGSVGElement | null>(null);
const canvasWrap = ref<HTMLElement | null>(null);
const assetUrls = reactive<Record<string, string>>({});
const form = reactive({
  title: "쿠팡 일일 작업계획",
  work_date: todayKst(),
  floor: "4F",
  workplace: "지하1층 2번코어",
  work_description: "",
  hazard: "안전고리 미체결로 인한 추락 위험",
  control: "적정 안전고리 체결 및 관리감독자 확인",
  contractor_name: "부현전기",
  manager_name: "",
  worker_count: 0,
  notes: "",
});
const drawing = reactive<Drawing>({ width: 1600, height: 1000, background_asset_id: null, objects: [] });
const selectedObject = computed(() => drawing.objects.find((item) => item.id === selectedId.value) || null);
let dragState: { id: string; offsetX: number; offsetY: number } | null = null;

onMounted(async () => {
  try {
    const { data } = await api.get("/coupang-mvp/access");
    Object.assign(form, data.defaults || {});
    await loadDocuments();
  } catch (error: any) {
    accessError.value = error?.response?.data?.detail || "쿠팡 MVP에 접근할 수 없습니다.";
  } finally {
    loading.value = false;
  }
});

function notify(text: string, isError = false) {
  message.value = text;
  messageIsError.value = isError;
  window.setTimeout(() => {
    if (message.value === text) message.value = "";
  }, 3500);
}

function markDirty() {
  dirty.value = true;
}

function resetDrawing() {
  drawing.width = 1600;
  drawing.height = 1000;
  drawing.background_asset_id = null;
  drawing.objects.splice(0);
  selectedId.value = null;
}

function newDocument() {
  currentId.value = null;
  Object.assign(form, {
    title: "쿠팡 일일 작업계획",
    work_date: todayKst(),
    floor: "4F",
    workplace: "지하1층 2번코어",
    work_description: "",
    hazard: "안전고리 미체결로 인한 추락 위험",
    control: "적정 안전고리 체결 및 관리감독자 확인",
    contractor_name: "부현전기",
    manager_name: "",
    worker_count: 0,
    notes: "",
  });
  resetDrawing();
  dirty.value = false;
  activeTab.value = "form";
}

function makeId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function addIcon(tool: { label: string; glyph: string; color: string }) {
  const index = drawing.objects.length % 6;
  const object: DrawingObject = {
    id: makeId("icon"),
    type: "icon",
    x: 650 + index * 28,
    y: 380 + index * 24,
    w: 120,
    h: 120,
    label: tool.label,
    glyph: tool.glyph,
    color: tool.color,
  };
  drawing.objects.push(object);
  selectedId.value = object.id;
  markDirty();
}

function svgPoint(event: PointerEvent) {
  const rect = svgRef.value!.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * drawing.width,
    y: ((event.clientY - rect.top) / rect.height) * drawing.height,
  };
}

function startDrag(event: PointerEvent, object: DrawingObject) {
  selectedId.value = object.id;
  const point = svgPoint(event);
  dragState = { id: object.id, offsetX: point.x - object.x, offsetY: point.y - object.y };
  svgRef.value?.setPointerCapture(event.pointerId);
}

function moveObject(event: PointerEvent) {
  if (!dragState) return;
  const object = drawing.objects.find((item) => item.id === dragState!.id);
  if (!object) return;
  const point = svgPoint(event);
  object.x = Math.round(Math.max(0, Math.min(drawing.width - object.w, point.x - dragState.offsetX)));
  object.y = Math.round(Math.max(0, Math.min(drawing.height - object.h - 55, point.y - dragState.offsetY)));
  markDirty();
}

function endDrag(event: PointerEvent) {
  if (dragState) svgRef.value?.releasePointerCapture?.(event.pointerId);
  dragState = null;
}

function resizeSelected() {
  const object = selectedObject.value;
  if (!object) return;
  object.h = object.type === "photo" ? Math.round(object.w * 0.7) : object.w;
  markDirty();
}

function moveLayer(direction: number) {
  const index = drawing.objects.findIndex((item) => item.id === selectedId.value);
  const next = Math.max(0, Math.min(drawing.objects.length - 1, index + direction));
  if (index < 0 || next === index) return;
  const [object] = drawing.objects.splice(index, 1);
  drawing.objects.splice(next, 0, object);
  markDirty();
}

function removeSelected() {
  const index = drawing.objects.findIndex((item) => item.id === selectedId.value);
  if (index < 0) return;
  drawing.objects.splice(index, 1);
  selectedId.value = null;
  markDirty();
}

async function uploadFile(file: File) {
  const body = new FormData();
  body.append("file", file);
  const { data } = await api.post("/coupang-mvp/assets", body, { headers: { "Content-Type": "multipart/form-data" } });
  assetUrls[data.asset_id] = await fileToDataUrl(file);
  return data;
}

function fileToDataUrl(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function handleUpload(event: Event, kind: "background" | "photo") {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  uploading.value = true;
  try {
    const asset = await uploadFile(file);
    if (kind === "background") {
      drawing.background_asset_id = asset.asset_id;
    } else {
      const ratio = Math.max(0.45, Math.min(1.4, asset.height / asset.width));
      const object: DrawingObject = {
        id: makeId("photo"),
        type: "photo",
        x: 570,
        y: 330,
        w: 460,
        h: Math.round(460 * ratio),
        label: "현장사진",
        asset_id: asset.asset_id,
      };
      drawing.objects.push(object);
      selectedId.value = object.id;
    }
    markDirty();
    notify(kind === "background" ? "도면 배경을 올렸습니다." : "현장사진을 도면에 추가했습니다.");
  } catch (error: any) {
    notify(error?.response?.data?.detail || "이미지 업로드에 실패했습니다.", true);
  } finally {
    uploading.value = false;
    input.value = "";
  }
}

const uploadBackground = (event: Event) => handleUpload(event, "background");
const uploadPhoto = (event: Event) => handleUpload(event, "photo");

async function loadAsset(assetId?: string | null) {
  if (!assetId || assetUrls[assetId]) return;
  try {
    const { data } = await api.get(`/coupang-mvp/assets/${assetId}`, { responseType: "blob" });
    assetUrls[assetId] = await fileToDataUrl(data);
  } catch {
    notify("저장된 이미지 일부를 불러오지 못했습니다.", true);
  }
}

async function hydrateAssets() {
  const ids = [
    drawing.background_asset_id,
    ...drawing.objects.map((item) => item.asset_id),
  ].filter(Boolean) as string[];
  await Promise.all([...new Set(ids)].map(loadAsset));
}

async function loadDocuments() {
  try {
    const { data } = await api.get("/coupang-mvp/documents");
    documents.value = data.items || [];
  } catch (error: any) {
    notify(error?.response?.data?.detail || "저장 내역을 불러오지 못했습니다.", true);
  }
}

async function openDocument(document: StoredDocument) {
  if (dirty.value && !window.confirm("저장하지 않은 변경사항이 있습니다. 이 문서를 여시겠습니까?")) return;
  currentId.value = document.id;
  for (const key of Object.keys(form) as Array<keyof typeof form>) {
    if (key in document) (form[key] as any) = document[key];
  }
  resetDrawing();
  Object.assign(drawing, {
    width: document.drawing?.width || 1600,
    height: document.drawing?.height || 1000,
    background_asset_id: document.drawing?.background_asset_id || null,
  });
  drawing.objects.push(...(document.drawing?.objects || []).map((item: DrawingObject) => ({ ...item })));
  await hydrateAssets();
  dirty.value = false;
  activeTab.value = "drawing";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function payload() {
  return {
    ...form,
    worker_count: Number(form.worker_count || 0),
    drawing: JSON.parse(JSON.stringify(drawing)),
  };
}

async function saveDocument() {
  if (!form.title.trim() || !form.work_date) {
    activeTab.value = "form";
    notify("작업일과 문서 제목을 입력해주세요.", true);
    return;
  }
  saving.value = true;
  try {
    const { data } = currentId.value
      ? await api.put(`/coupang-mvp/documents/${currentId.value}`, payload())
      : await api.post("/coupang-mvp/documents", payload());
    currentId.value = data.id;
    dirty.value = false;
    await loadDocuments();
    notify("도면과 작업정보를 서버에 저장했습니다.");
  } catch (error: any) {
    notify(error?.response?.data?.detail || "저장에 실패했습니다.", true);
  } finally {
    saving.value = false;
  }
}

async function downloadPng() {
  if (!svgRef.value) return;
  try {
    const clone = svgRef.value.cloneNode(true) as SVGSVGElement;
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    clone.setAttribute("width", String(drawing.width));
    clone.setAttribute("height", String(drawing.height));
    const source = new XMLSerializer().serializeToString(clone);
    const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = reject;
      image.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = drawing.width;
    canvas.height = drawing.height;
    canvas.getContext("2d")!.drawImage(image, 0, 0);
    URL.revokeObjectURL(url);
    const link = document.createElement("a");
    link.download = `${form.work_date}_${form.floor}_쿠팡작업도면.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
    notify("현재 도면을 PNG로 저장했습니다.");
  } catch {
    notify("도면 이미지 생성에 실패했습니다.", true);
  }
}

function fitDrawing() {
  canvasWrap.value?.scrollTo({ left: 0, top: 0, behavior: "smooth" });
}
</script>

<style scoped>
.coupang-page { padding: 0 0 92px; color: #172033; }
.hero { display: flex; justify-content: space-between; gap: 24px; align-items: center; padding: 24px 28px; margin-bottom: 18px; color: #fff; border-radius: 22px; background: linear-gradient(125deg, #0b1736, #173f70 65%, #167e87); box-shadow: 0 16px 36px rgba(15, 23, 42, .18); }
.hero h2 { margin: 2px 0 6px; font-size: 28px; }.hero p { margin: 0; color: #dbeafe; }.eyebrow { font-size: 11px; letter-spacing: .18em; font-weight: 800; color: #67e8f9 !important; }
.save-state { flex: none; padding: 8px 12px; border: 1px solid rgba(255,255,255,.3); border-radius: 999px; font-size: 12px; font-weight: 800; background: rgba(15,23,42,.35); }.save-state.saved { background: #0f766e; }
.workspace { display: grid; grid-template-columns: minmax(260px, .72fr) minmax(520px, 1.8fr) minmax(230px, .62fr); gap: 16px; align-items: start; }
.form-panel,.drawing-panel,.history-panel,.state-card { background: #fff; border: 1px solid #dfe7f0; border-radius: 18px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,.06); }
.panel-title { display: flex; justify-content: space-between; align-items: start; gap: 12px; margin-bottom: 14px; }.panel-title h3 { margin: 0; font-size: 18px; }.drawing-heading p { margin: 5px 0 0; font-size: 12px; color: #64748b; }
label { display: grid; gap: 6px; margin-bottom: 12px; font-size: 12px; font-weight: 800; color: #475569; }
input,textarea,select { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 10px; padding: 10px 11px; font: inherit; font-weight: 500; color: #0f172a; background: #fff; } textarea { resize: vertical; }.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
button { font: inherit; cursor: pointer; }.text-button { padding: 0; border: 0; color: #2563eb; background: transparent; font-size: 12px; font-weight: 800; }
.upload-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }.upload-button { display: flex; justify-content: center; align-items: center; min-height: 44px; margin: 0; padding: 0 12px; border: 1px dashed #64748b; border-radius: 12px; color: #1e3a5f; background: #eff6ff; cursor: pointer; }.upload-button.accent { color: #075985; border-color: #0891b2; background: #ecfeff; }.upload-button input { display: none; }
.tool-strip { display: flex; gap: 7px; padding: 2px 0 12px; overflow-x: auto; }.tool-strip button { flex: 0 0 auto; display: grid; justify-items: center; gap: 2px; min-width: 68px; padding: 7px 8px; border: 1px solid #dbe3ed; border-radius: 11px; color: #334155; background: #fff; font-size: 11px; font-weight: 800; }.tool-strip button span { font-size: 22px; }
.canvas-wrap { width: 100%; overflow: auto; border: 1px solid #94a3b8; border-radius: 14px; background: #e2e8f0; }.drawing-svg { display: block; width: 100%; min-width: 520px; aspect-ratio: 1.6; background: #fff; touch-action: none; user-select: none; }.drawing-object { cursor: grab; }.drawing-object:active { cursor: grabbing; }.empty-drawing text { fill: #64748b; font-size: 34px; font-weight: 800; }.empty-drawing .small { font-size: 22px; font-weight: 500; }
.selection-tools { display: grid; grid-template-columns: 1.3fr 1fr .55fr auto; gap: 10px; align-items: end; margin-top: 12px; padding: 12px; border: 1px solid #bfdbfe; border-radius: 12px; background: #eff6ff; }.selection-tools label { margin: 0; }.selection-actions { display: flex; gap: 5px; }.selection-actions button { min-height: 38px; border: 1px solid #cbd5e1; border-radius: 9px; background: #fff; }.selection-actions .danger { color: #b91c1c; }
.history-panel { max-height: 720px; overflow: auto; }.history-item { display: grid; width: 100%; gap: 5px; margin-bottom: 8px; padding: 12px; text-align: left; border: 1px solid #e2e8f0; border-radius: 11px; background: #f8fafc; }.history-item.active { border-color: #2563eb; background: #eff6ff; }.history-item span,.empty-list { color: #64748b; font-size: 11px; }
.action-bar { position: fixed; z-index: 20; right: 24px; bottom: 18px; display: flex; gap: 8px; padding: 8px; border: 1px solid #dbe3ed; border-radius: 16px; background: rgba(255,255,255,.94); box-shadow: 0 12px 35px rgba(15,23,42,.22); backdrop-filter: blur(10px); }.action-bar button { min-height: 46px; padding: 0 20px; border-radius: 11px; font-weight: 900; }.primary-action { color: #fff; border: 0; background: #0f766e; }.primary-action:disabled { opacity: .55; }.secondary-action { color: #1e3a5f; border: 1px solid #94a3b8; background: #fff; }
.mobile-tabs { display: none; }.toast { position: fixed; z-index: 30; left: 50%; bottom: 88px; transform: translateX(-50%); padding: 11px 16px; border-radius: 11px; color: #fff; background: #0f766e; box-shadow: 0 8px 30px rgba(0,0,0,.25); }.toast.error,.state-card.error { color: #b91c1c; background: #fff1f2; }
@media (max-width: 1180px) { .workspace { grid-template-columns: 280px 1fr; }.history-panel { grid-column: 1 / -1; max-height: none; }.history-item { display: inline-grid; width: min(280px, 100%); margin-right: 8px; } }
@media (max-width: 760px) {
  .coupang-page { padding-bottom: 86px; }.hero { align-items: start; padding: 18px; border-radius: 16px; }.hero h2 { font-size: 21px; }.hero p:not(.eyebrow) { font-size: 12px; }.save-state { padding: 6px 8px; }
  .mobile-tabs { position: sticky; z-index: 12; top: 0; display: grid; grid-template-columns: repeat(3,1fr); gap: 4px; margin: 0 0 10px; padding: 4px; border: 1px solid #dbe3ed; border-radius: 12px; background: #fff; }.mobile-tabs button { min-height: 40px; border: 0; border-radius: 9px; color: #64748b; background: transparent; font-size: 12px; font-weight: 900; }.mobile-tabs button.active { color: #fff; background: #173f70; }
  .workspace { display: block; }.form-panel,.drawing-panel,.history-panel { border-radius: 14px; padding: 13px; }.mobile-hidden { display: none; }.field-grid { grid-template-columns: 1fr 1fr; }.upload-row { grid-template-columns: 1fr; }.drawing-svg { min-width: 460px; }.selection-tools { grid-template-columns: 1fr 1fr; }.selection-actions { grid-column: 1/-1; }.selection-actions button { flex: 1; }.history-item { display: grid; width: 100%; margin-right: 0; }
  .action-bar { right: 10px; bottom: 10px; left: 10px; }.action-bar button { flex: 1; padding: 0 9px; font-size: 13px; }.toast { width: calc(100% - 40px); box-sizing: border-box; text-align: center; }
}
</style>
