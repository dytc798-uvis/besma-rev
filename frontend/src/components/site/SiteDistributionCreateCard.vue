<template>
  <section class="ops-card">
    <h2>③ 배포 생성</h2>
    <p v-if="!planId" class="msg hint">작업일보와 항목을 먼저 생성하세요.</p>
    <p v-else-if="!hasAdoptedItems" class="msg hint">위험요인을 채택한 후 배포할 수 있습니다.</p>
    <template v-else>
      <div class="field-row">
        <label>배포일</label>
        <input type="date" v-model="targetDate" />
      </div>

      <div class="worker-section">
        <div class="worker-header">
          <strong>배포 대상 근로자</strong>
          <button class="btn-text" :disabled="workersLoading" @click="loadWorkers">
            {{ workersLoading ? "조회 중..." : "목록 새로고침" }}
          </button>
        </div>

        <div v-if="workers.length > 0" class="worker-select">
          <label class="worker-row select-all">
            <input type="checkbox" :checked="allSelected" @change="toggleAll" />
            <span>전체 선택 ({{ selectedPersonIds.length }}/{{ workers.length }}명)</span>
          </label>
          <label v-for="w in workers" :key="w.person_id" class="worker-row">
            <input type="checkbox" :value="w.person_id" v-model="selectedPersonIds" />
            <span>{{ w.name }}</span>
            <span class="worker-meta">{{ w.department_name ?? "" }} {{ w.position_name ?? "" }}</span>
          </label>
        </div>
        <div v-else-if="!workersLoading" class="msg hint">
          근로자 목록이 비어 있습니다. 근로자 데이터를 확인하세요.
        </div>
      </div>

      <button
        class="btn-primary"
        :disabled="distributeLoading || selectedPersonIds.length === 0"
        @click="createDistribution"
      >
        {{ distributeLoading ? "배포 생성 중..." : `배포 생성 (${selectedPersonIds.length}명)` }}
      </button>
      <p v-if="error" class="msg error">{{ error }}</p>
      <p v-if="success" class="msg success">{{ success }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { api } from "@/services/api";
import { todayKst } from "@/utils/datetime";

interface SiteWorker {
  person_id: number;
  employment_id: number;
  name: string;
  department_name: string | null;
  position_name: string | null;
}

const props = defineProps<{
  planId: number | null;
  siteId: number;
  hasAdoptedItems: boolean;
}>();
const emit = defineEmits<{
  (e: "distribution-created", dist: any): void;
}>();

const today = todayKst();
const targetDate = ref(today);
const workers = ref<SiteWorker[]>([]);
const selectedPersonIds = ref<number[]>([]);
const workersLoading = ref(false);
const distributeLoading = ref(false);
const error = ref("");
const success = ref("");

const allSelected = computed(
  () => workers.value.length > 0 && selectedPersonIds.value.length === workers.value.length,
);

function toggleAll() {
  if (allSelected.value) {
    selectedPersonIds.value = [];
  } else {
    selectedPersonIds.value = workers.value.map((w) => w.person_id);
  }
}

async function loadWorkers() {
  workersLoading.value = true;
  error.value = "";
  try {
    const res = await api.get(`/sites/${props.siteId}/workers`, {
      params: { target_date: targetDate.value },
    });
    workers.value = res.data;
    selectedPersonIds.value = workers.value.map((w) => w.person_id);
  } catch (err: any) {
    error.value = err?.response?.data?.detail ?? "근로자 목록 조회에 실패했습니다.";
  } finally {
    workersLoading.value = false;
  }
}

async function createDistribution() {
  if (!props.planId) return;
  distributeLoading.value = true;
  error.value = "";
  success.value = "";
  try {
    const visibleFrom = new Date().toISOString();
    const res = await api.post("/daily-work-plans/distributions", {
      plan_id: props.planId,
      target_date: targetDate.value,
      visible_from: visibleFrom,
      person_ids: selectedPersonIds.value,
    });
    success.value = `배포 #${res.data.id} 생성 완료 (${res.data.worker_count}명)`;
    emit("distribution-created", res.data);
  } catch (err: any) {
    error.value = err?.response?.data?.detail ?? "배포 생성에 실패했습니다.";
  } finally {
    distributeLoading.value = false;
  }
}

watch(() => props.hasAdoptedItems, (v) => {
  if (v && workers.value.length === 0) loadWorkers();
});

watch(
  () => props.planId,
  () => {
    workers.value = [];
    selectedPersonIds.value = [];
    error.value = "";
    success.value = "";
    if (props.hasAdoptedItems) {
      loadWorkers();
    }
  },
);

onMounted(() => {
  if (props.hasAdoptedItems) loadWorkers();
});
</script>
