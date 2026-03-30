<template>
  <div class="paste-card">
    <!-- Step 1: Paste -->
    <div v-if="step === 'paste'">
      <textarea
        v-model="rawText"
        placeholder="ERP / 엑셀 / 문서에서 복사한 작업일보를 여기에 붙여넣으세요"
        rows="10"
        class="paste-area"
      ></textarea>
      <button
        class="btn-primary"
        :disabled="!rawText.trim()"
        @click="analyze"
      >
        분석하기
      </button>
    </div>

    <!-- Step 2: Preview -->
    <div v-else-if="step === 'preview' && parsed">
      <div class="parsed-summary">
        <div v-if="parsed.work_date"><strong>작업일:</strong> {{ parsed.work_date }}</div>
        <div v-if="parsed.site_name"><strong>현장:</strong> {{ parsed.site_name }}</div>
        <div v-if="parsed.manager"><strong>담당자:</strong> {{ parsed.manager }}</div>
        <div><strong>추출 항목:</strong> {{ editableItems.length }}건</div>
      </div>

      <div class="field-row">
        <label>작업일</label>
        <input type="date" v-model="selectedDate" />
      </div>

      <div class="items-preview">
        <div
          v-for="(item, idx) in editableItems"
          :key="idx"
          class="preview-item"
        >
          <div class="preview-item-header">
            <span class="preview-idx">{{ idx + 1 }}</span>
            <input v-model="item.work_name" class="preview-input" />
            <button class="btn-icon" @click="removeItem(idx)" title="삭제">✕</button>
          </div>
          <div v-if="item.workers_text" class="preview-workers">{{ item.workers_text }}</div>
        </div>
      </div>

      <div class="add-item-row">
        <input
          v-model="newItemName"
          placeholder="항목 직접 추가"
          class="preview-input"
          @keydown.enter="addManualItem"
        />
        <button class="btn-secondary" :disabled="!newItemName.trim()" @click="addManualItem">추가</button>
      </div>

      <div class="preview-actions">
        <button class="btn-secondary" @click="step = 'paste'">← 다시 입력</button>
        <button
          class="btn-primary"
          :disabled="creating || editableItems.length === 0"
          @click="createPlanAndItems"
        >
          {{ creating ? "생성 중..." : `작업일보 생성 (${editableItems.length}건)` }}
        </button>
      </div>
    </div>

    <!-- Step 3: Done -->
    <div v-else-if="step === 'done'">
      <div class="done-msg">
        작업일보 #{{ createdPlanId }} 생성 완료 ({{ createdItemCount }}건)
      </div>
      <button class="btn-secondary" @click="reset">새로 입력하기</button>
    </div>

    <p v-if="error" class="msg error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue";
import { api } from "@/services/api";
import { parsePastedText, type ParsedPlanItem, type ParsedPlanResult } from "@/utils/sitePlanPasteParser";

const props = defineProps<{
  siteId: number;
}>();
const emit = defineEmits<{
  (e: "plan-created", plan: any): void;
}>();

const step = ref<"paste" | "preview" | "done">("paste");
const rawText = ref("");
const parsed = ref<ParsedPlanResult | null>(null);
const editableItems = reactive<ParsedPlanItem[]>([]);
const selectedDate = ref(new Date().toISOString().slice(0, 10));
const newItemName = ref("");
const creating = ref(false);
const error = ref("");
const createdPlanId = ref<number | null>(null);
const createdItemCount = ref(0);

function analyze() {
  error.value = "";
  const result = parsePastedText(rawText.value);
  parsed.value = result;
  editableItems.splice(0, editableItems.length, ...result.items);
  if (result.work_date) selectedDate.value = result.work_date;
  if (editableItems.length === 0) {
    error.value = "작업항목을 추출하지 못했습니다. 텍스트를 확인하거나 아래에서 직접 추가하세요.";
  }
  step.value = "preview";
}

function removeItem(idx: number) {
  editableItems.splice(idx, 1);
}

function addManualItem() {
  if (!newItemName.value.trim()) return;
  editableItems.push({
    work_name: newItemName.value.trim(),
    work_description: newItemName.value.trim(),
    team_label: "",
    workers_text: "",
  });
  newItemName.value = "";
}

async function createPlanAndItems() {
  creating.value = true;
  error.value = "";
  try {
    const planRes = await api.post("/daily-work-plans", {
      site_id: props.siteId,
      work_date: selectedDate.value,
    });
    const plan = planRes.data;
    let successCount = 0;

    for (const item of editableItems) {
      const desc = item.workers_text
        ? `${item.work_description} (${item.workers_text})`
        : item.work_description;
      try {
        await api.post(`/daily-work-plans/${plan.id}/items`, {
          work_name: item.work_name,
          work_description: desc,
          team_label: item.team_label || null,
        });
        successCount++;
      } catch {
        /* continue with remaining items */
      }
    }

    createdPlanId.value = plan.id;
    createdItemCount.value = successCount;
    step.value = "done";

    const refreshRes = await api.get(`/daily-work-plans/${plan.id}`);
    emit("plan-created", refreshRes.data);
  } catch (err: any) {
    error.value = err?.response?.data?.detail ?? "작업일보 생성에 실패했습니다.";
  } finally {
    creating.value = false;
  }
}

function reset() {
  step.value = "paste";
  rawText.value = "";
  parsed.value = null;
  editableItems.splice(0, editableItems.length);
  error.value = "";
  createdPlanId.value = null;
  createdItemCount.value = 0;
}
</script>
