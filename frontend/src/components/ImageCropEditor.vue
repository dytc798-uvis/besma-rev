<template>
  <section class="crop-editor">
    <div class="crop-head">
      <div>
        <strong>사진 크롭·회전</strong>
        <small>원본은 보존되고 출력할 영역만 저장됩니다.</small>
      </div>
      <div class="rotate-buttons">
        <button type="button" @click="rotate(-90)">↶ 90°</button>
        <button type="button" @click="rotate(90)">↷ 90°</button>
        <button type="button" @click="reset">초기화</button>
      </div>
    </div>
    <div class="preview-stage">
      <img v-if="previewUrl" :src="previewUrl" alt="크롭 미리보기" :style="previewStyle" />
    </div>
    <div class="crop-controls">
      <label>왼쪽 <input :value="percent(modelValue.crop_left)" type="range" min="0" max="45" @input="setCrop('crop_left', $event)" /></label>
      <label>오른쪽 <input :value="percent(modelValue.crop_right)" type="range" min="0" max="45" @input="setCrop('crop_right', $event)" /></label>
      <label>위 <input :value="percent(modelValue.crop_top)" type="range" min="0" max="45" @input="setCrop('crop_top', $event)" /></label>
      <label>아래 <input :value="percent(modelValue.crop_bottom)" type="range" min="0" max="45" @input="setCrop('crop_bottom', $event)" /></label>
    </div>
    <label v-if="showCaption" class="caption-field">
      사진 설명
      <input :value="modelValue.caption || ''" maxlength="500" placeholder="예: 작업구간 안전점검" @input="setCaption" />
    </label>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";

export interface ImageTransform {
  rotation_degrees: number;
  crop_left: number;
  crop_top: number;
  crop_right: number;
  crop_bottom: number;
  caption?: string;
}

const props = withDefaults(defineProps<{
  file: File | null;
  modelValue: ImageTransform;
  showCaption?: boolean;
}>(), { showCaption: false });
const emit = defineEmits<{ (event: "update:modelValue", value: ImageTransform): void }>();
const previewUrl = ref("");

watch(() => props.file, (file) => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = file ? URL.createObjectURL(file) : "";
}, { immediate: true });
onBeforeUnmount(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
});

const previewStyle = computed(() => ({
  transform: `rotate(${props.modelValue.rotation_degrees || 0}deg)`,
  clipPath: `inset(${percent(props.modelValue.crop_top)}% ${percent(props.modelValue.crop_right)}% ${percent(props.modelValue.crop_bottom)}% ${percent(props.modelValue.crop_left)}%)`,
}));

function percent(value: number) {
  return Math.round((Number(value) || 0) * 100);
}

function update(patch: Partial<ImageTransform>) {
  emit("update:modelValue", { ...props.modelValue, ...patch });
}

function rotate(delta: number) {
  update({ rotation_degrees: ((props.modelValue.rotation_degrees || 0) + delta + 360) % 360 });
}

function setCrop(key: keyof Pick<ImageTransform, "crop_left" | "crop_top" | "crop_right" | "crop_bottom">, event: Event) {
  update({ [key]: Number((event.target as HTMLInputElement).value) / 100 });
}

function setCaption(event: Event) {
  update({ caption: (event.target as HTMLInputElement).value });
}

function reset() {
  emit("update:modelValue", {
    rotation_degrees: 0,
    crop_left: 0,
    crop_top: 0,
    crop_right: 0,
    crop_bottom: 0,
    caption: props.modelValue.caption || "",
  });
}
</script>

<style scoped>
.crop-editor { margin: -4px 0 18px; padding: 14px; border: 1px solid #b9d7d4; border-radius: 14px; background: #f7fcfb; }
.crop-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.crop-head div:first-child { display: grid; gap: 3px; }
.crop-head small { color: #64748b; }
.rotate-buttons { display: flex; flex-wrap: wrap; gap: 6px; }
button { min-height: 38px; padding: 7px 11px; border: 1px solid #9bb8b8; border-radius: 9px; background: white; color: #164e63; font-weight: 800; cursor: pointer; }
.preview-stage { display: grid; place-items: center; min-height: 220px; max-height: 390px; margin: 12px 0; overflow: hidden; border-radius: 10px; background: #1f2937; }
.preview-stage img { display: block; max-width: 90%; max-height: 350px; object-fit: contain; transition: transform .15s ease, clip-path .15s ease; }
.crop-controls { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 14px; }
.crop-controls label, .caption-field { display: grid; gap: 5px; color: #334155; font-size: 12px; font-weight: 800; }
.crop-controls input { width: 100%; }
.caption-field { margin-top: 11px; }
.caption-field input { min-height: 42px; padding: 9px 10px; border: 1px solid #cbd5e1; border-radius: 9px; font: inherit; }
@media (max-width: 680px) {
  .crop-head { align-items: stretch; flex-direction: column; }
  .rotate-buttons button { flex: 1; }
  .crop-controls { grid-template-columns: 1fr; }
  .preview-stage { min-height: 260px; }
}
</style>
