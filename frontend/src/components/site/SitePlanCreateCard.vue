<template>
  <section class="ops-card">
    <h2>① 작업일보 생성</h2>

    <div v-if="currentPlan" class="plan-badge">
      <span>작업일보 #{{ currentPlan.id }} ({{ currentPlan.work_date }})</span>
      <button class="btn-text" @click="$emit('reset-plan')">새로 만들기</button>
    </div>

    <template v-else>
      <div class="tab-bar">
        <button
          :class="['tab-btn', { active: tab === 'paste' }]"
          @click="tab = 'paste'"
        >
          복사 붙여넣기
        </button>
        <button
          :class="['tab-btn', { active: tab === 'manual' }]"
          @click="tab = 'manual'"
        >
          직접 입력
        </button>
      </div>

      <!-- Paste tab (primary) -->
      <SitePastePlanImportCard
        v-if="tab === 'paste'"
        :site-id="siteId"
        @plan-created="(plan: any) => $emit('plan-created', plan)"
      />

      <!-- Manual tab (secondary) -->
      <div v-else>
        <div class="field-row">
          <label>작업일</label>
          <input type="date" v-model="workDate" />
        </div>
        <button class="btn-primary" :disabled="loading" @click="createPlan">
          {{ loading ? "생성 중..." : "작업일보 생성" }}
        </button>
        <p v-if="error" class="msg error">{{ error }}</p>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { api } from "@/services/api";
import SitePastePlanImportCard from "./SitePastePlanImportCard.vue";

const props = defineProps<{
  siteId: number;
  currentPlan: { id: number; work_date: string; status: string } | null;
}>();
const emit = defineEmits<{
  (e: "plan-created", plan: any): void;
  (e: "reset-plan"): void;
}>();

const tab = ref<"paste" | "manual">("paste");
const today = new Date().toISOString().slice(0, 10);
const workDate = ref(today);
const loading = ref(false);
const error = ref("");

async function createPlan() {
  loading.value = true;
  error.value = "";
  try {
    const res = await api.post("/daily-work-plans", {
      site_id: props.siteId,
      work_date: workDate.value,
    });
    emit("plan-created", res.data);
  } catch (err: any) {
    error.value = err?.response?.data?.detail ?? "작업일보 생성에 실패했습니다.";
  } finally {
    loading.value = false;
  }
}
</script>
