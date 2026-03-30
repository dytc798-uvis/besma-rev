<template>
  <div class="card">
    <div class="card-title">SITE_MANAGER 테스트 허브</div>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px">
      <label class="form-field">
        <span>site_id</span>
        <input v-model.number="siteId" type="text" />
      </label>
      <label class="form-field">
        <span>work_date (YYYY-MM-DD)</span>
        <input v-model="workDate" type="text" />
      </label>
      <label class="form-field">
        <span>plan_id</span>
        <input v-model.number="planId" type="text" />
      </label>
      <label class="form-field">
        <span>item_id</span>
        <input v-model.number="itemId" type="text" />
      </label>
    </div>

    <div class="toolbar" style="margin-top: 12px">
      <div class="toolbar-actions">
        <button class="primary" @click="createPlan">1) 계획 생성</button>
        <button class="primary" @click="createItem">2) 항목 추가</button>
        <button class="primary" @click="recommend">3) 추천</button>
        <button class="primary" @click="adopt">4) 채택</button>
        <button class="primary" @click="assemble">5) Assemble</button>
      </div>
    </div>

    <div style="margin-top: 8px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px">
      <label class="form-field">
        <span>distribution target_date</span>
        <input v-model="targetDate" type="text" />
      </label>
      <label class="form-field">
        <span>person_ids (comma)</span>
        <input v-model="personIdsText" type="text" />
      </label>
    </div>

    <div class="toolbar" style="margin-top: 10px">
      <div class="toolbar-actions">
        <button class="primary" @click="distribute">6) Distribution 생성</button>
        <button class="primary" @click="getDistribution">7) 배포 조회(access_token 확보)</button>
        <button class="primary" @click="startTbm">8) TBM 시작</button>
        <button class="primary" @click="pingPresence">9) Presence ping</button>
      </div>
    </div>

    <label class="form-field" style="margin-top: 10px">
      <span>distribution_id</span>
      <input v-model.number="distributionId" type="text" />
    </label>
    <p style="margin-top: 6px; color: #6b7280">
      TBM 상태: <strong>{{ tbmActive ? "시작됨" : "미시작" }}</strong>
      <span v-if="tbmStartedAt"> / 시작시각: {{ tbmStartedAt }}</span>
    </p>

    <pre style="margin-top: 12px; white-space: pre-wrap">{{ resultText }}</pre>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { api } from "@/services/api";

const siteId = ref<number>(1);
const workDate = ref("2026-03-18");
const planId = ref<number | null>(null);
const itemId = ref<number | null>(null);
const targetDate = ref("2026-03-18");
const personIdsText = ref("1");
const distributionId = ref<number | null>(null);
const pickedRevisionId = ref<number | null>(null);
const resultText = ref("");
const tbmActive = ref(false);
const tbmStartedAt = ref<string | null>(null);

function setResult(payload: unknown) {
  resultText.value = JSON.stringify(payload, null, 2);
}

async function createPlan() {
  const res = await api.post("/daily-work-plans", {
    site_id: siteId.value,
    work_date: workDate.value,
  });
  planId.value = res.data.id;
  setResult(res.data);
}

async function createItem() {
  if (!planId.value) return;
  const res = await api.post(`/daily-work-plans/${planId.value}/items`, {
    work_name: "테스트 작업",
    work_description: "TBM 테스트용 작업 위험요인 점검",
    team_label: "A",
  });
  itemId.value = res.data.id;
  setResult(res.data);
}

async function recommend() {
  if (!itemId.value) return;
  const res = await api.post(`/daily-work-plan-items/${itemId.value}/recommend-risks`, { top_n: 10 });
  setResult(res.data);
}

async function adopt() {
  if (!itemId.value) return;
  const refs = await api.get(`/daily-work-plan-items/${itemId.value}/risk-refs`);
  const first = refs.data?.[0];
  if (!first) {
    setResult({ error: "추천 결과 없음" });
    return;
  }
  pickedRevisionId.value = first.risk_revision_id;
  const res = await api.post(`/daily-work-plan-items/${itemId.value}/adopt-risks`, {
    risk_revision_ids: [pickedRevisionId.value],
  });
  setResult(res.data);
}

async function assemble() {
  const res = await api.post("/daily-work-plans/assemble-document", {
    site_id: siteId.value,
    work_date: workDate.value,
  });
  setResult(res.data);
}

async function distribute() {
  if (!planId.value) return;
  const personIds = personIdsText.value
    .split(",")
    .map((v) => Number(v.trim()))
    .filter((v) => Number.isFinite(v) && v > 0);
  const visibleFrom = new Date(Date.now() - 60_000).toISOString();
  const res = await api.post("/daily-work-plans/distributions", {
    plan_id: planId.value,
    target_date: targetDate.value,
    visible_from: visibleFrom,
    person_ids: personIds,
  });
  distributionId.value = res.data.id;
  setResult(res.data);
}

async function getDistribution() {
  if (!distributionId.value) return;
  const res = await api.get(`/daily-work-plans/distributions/${distributionId.value}`);
  tbmActive.value = !!res.data?.is_tbm_active;
  tbmStartedAt.value = res.data?.tbm_started_at ?? null;
  setResult(res.data);
}

async function startTbm() {
  if (!distributionId.value) return;
  const res = await api.post(`/daily-work-plans/distributions/${distributionId.value}/start-tbm`);
  tbmActive.value = !!res.data?.is_tbm_active;
  tbmStartedAt.value = res.data?.tbm_started_at ?? null;
  setResult(res.data);
}

async function pingPresence() {
  const res = await api.post("/daily-work-plans/admin-presence/ping", {
    site_id: siteId.value,
    lat: 37.1234,
    lng: 127.1234,
  });
  setResult(res.data);
}
</script>
