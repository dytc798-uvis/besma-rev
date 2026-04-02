<template>
  <div class="card" v-if="opinion">
    <div class="card-title">운영 아이디어 상세 / 조치</div>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; font-size: 13px">
      <div><strong>ID</strong> {{ opinion.id }}</div>
      <div><strong>제안자</strong> {{ opinion.reporter_type }}</div>
      <div><strong>유형</strong> {{ opinion.category }}</div>
      <div><strong>상태</strong> {{ opinion.status }}</div>
      <div style="grid-column: span 2">
        <strong>아이디어</strong>
        <div>{{ opinion.content }}</div>
      </div>
      <div><strong>적절성 점수</strong> {{ opinion.score_appropriateness ?? "-" }}</div>
      <div><strong>실행가능성 점수</strong> {{ opinion.score_actionability ?? "-" }}</div>
      <div style="grid-column: span 2">
        <strong>조치내용</strong>
        <div>{{ opinion.action_result ?? "-" }}</div>
      </div>
    </div>

    <div style="margin-top: 16px">
      <h3 style="font-size: 14px; margin-bottom: 8px">상태 / 조치 업데이트</h3>
      <form class="form-grid" @submit.prevent="update">
        <div class="form-field">
          <label>상태</label>
          <select v-model="status">
            <option value="RECEIVED">접수</option>
            <option value="REVIEWING">검토중</option>
            <option value="ACTIONED">조치완료</option>
            <option value="HOLD">보류</option>
          </select>
        </div>
        <div class="form-field">
          <label>적절성 점수</label>
          <input v-model.number="scoreAppropriateness" type="number" min="1" max="5" />
        </div>
        <div class="form-field">
          <label>실행가능성 점수</label>
          <input v-model.number="scoreActionability" type="number" min="1" max="5" />
        </div>
        <div class="form-field" style="grid-column: span 2">
          <label>조치내용</label>
          <textarea v-model="actionResult" rows="3" />
        </div>
        <div style="grid-column: span 2; display: flex; justify-content: flex-end; gap: 8px">
          <button type="submit" class="primary">저장</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { api } from "@/services/api";

interface OpinionDetail {
  id: number;
  site_id: number;
  category: string;
  content: string;
  reporter_type: string;
  status: string;
  score_appropriateness: number | null;
  score_actionability: number | null;
  action_result: string | null;
}

const route = useRoute();

const opinion = ref<OpinionDetail | null>(null);
const status = ref("RECEIVED");
const scoreAppropriateness = ref<number | null>(null);
const scoreActionability = ref<number | null>(null);
const actionResult = ref("");

async function load() {
  const res = await api.get(`/opinions/${route.params.id}`);
  opinion.value = res.data;
  status.value = opinion.value.status;
  scoreAppropriateness.value = opinion.value.score_appropriateness;
  scoreActionability.value = opinion.value.score_actionability;
  actionResult.value = opinion.value.action_result ?? "";
}

async function update() {
  if (!opinion.value) return;
  await api.put(`/opinions/${opinion.value.id}`, {
    status: status.value,
    score_appropriateness: scoreAppropriateness.value,
    score_actionability: scoreActionability.value,
    action_result: actionResult.value,
  });
  await load();
}

onMounted(load);
</script>

