<template>
  <section class="ops-card">
    <h2>② 작업항목 관리</h2>
    <p v-if="!planId" class="msg hint">작업일보를 먼저 생성하세요.</p>
    <template v-else>
      <div class="add-form">
        <div class="field-row">
          <label>작업명</label>
          <input v-model="newItem.work_name" placeholder="예: 전기배선 작업" />
        </div>
        <div class="field-row">
          <label>작업내용</label>
          <input v-model="newItem.work_description" placeholder="예: 2층 분전반 배선" />
        </div>
        <div class="field-row">
          <label>공종/팀</label>
          <input v-model="newItem.team_label" placeholder="선택사항" />
        </div>
        <button class="btn-secondary" :disabled="addLoading || !newItem.work_name" @click="addItem">
          {{ addLoading ? "추가 중..." : "항목 추가" }}
        </button>
      </div>
      <p v-if="addError" class="msg error">{{ addError }}</p>

      <div v-if="items.length === 0" class="msg hint">추가된 작업항목이 없습니다.</div>

      <div v-for="item in items" :key="item.id" class="item-card">
        <div class="item-header">
          <strong>{{ item.work_name }}</strong>
          <span class="badge" v-if="adoptionStatus[item.id]">채택완료</span>
        </div>
        <div class="item-desc">{{ item.work_description }}</div>
        <div v-if="item.team_label" class="item-team">공종: {{ item.team_label }}</div>

        <div class="item-actions">
          <button
            class="btn-small"
            :disabled="recLoading[item.id]"
            @click="recommendRisks(item.id)"
          >
            {{ recLoading[item.id] ? "조회 중..." : "위험요인 추천" }}
          </button>
          <button
            class="btn-small adopt"
            v-if="recommendations[item.id]?.length"
            :disabled="adoptLoading[item.id] || !(selectedRevisions[item.id]?.length)"
            @click="adoptRisks(item.id)"
          >
            {{
              adoptLoading[item.id]
                ? "채택 중..."
                : selectedRevisions[item.id]?.length
                  ? `선택 채택 (${selectedRevisions[item.id]?.length}건)`
                  : "채택할 항목 선택 필요"
            }}
          </button>
        </div>

        <div v-if="recommendations[item.id]?.length" class="rec-list">
          <div class="rec-header">
            <span>추천 위험요인 ({{ recommendations[item.id].length }}건)</span>
            <button
              v-if="recommendations[item.id].length > defaultVisibleCount"
              class="btn-text"
              @click="toggleShowAll(item.id)"
            >
              {{ showAllRecommendations[item.id] ? "접기" : "더보기" }}
            </button>
          </div>
          <label
            v-for="rec in visibleRecommendations(item.id)"
            :key="rec.revision_id"
            class="rec-row"
          >
            <input
              type="checkbox"
              :value="rec.revision_id"
              v-model="selectedRevisions[item.id]"
              @change="adoptionStatus[item.id] = false"
            />
            <div class="rec-detail">
              <div><strong>위험요인:</strong> {{ rec.risk_factor }}</div>
              <div><strong>대책:</strong> {{ rec.countermeasure }}</div>
              <div class="rec-meta">위험도: {{ rec.risk_r ?? "-" }} | 매칭: {{ rec.score?.toFixed(1) ?? "-" }}</div>
            </div>
          </label>
        </div>
        <div v-if="noRiskOption[item.id]" class="no-risk-box">
          <label class="rec-row">
            <input type="checkbox" v-model="noRiskConfirmed[item.id]" @change="emitNoRisk(item.id)" />
            <div class="rec-detail">
              <div><strong>위험요인 없음</strong></div>
              <div>현재 추천 결과가 없어도 이 항목으로 배포를 진행할 수 있습니다.</div>
            </div>
          </label>
        </div>
        <p v-if="itemErrors[item.id]" class="msg error">{{ itemErrors[item.id] }}</p>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from "vue";
import { api } from "@/services/api";

interface PlanItem {
  id: number;
  work_name: string;
  work_description: string;
  team_label: string | null;
  risk_refs: any[];
}

interface Recommendation {
  revision_id: number;
  risk_factor: string;
  countermeasure: string;
  score: number | null;
  risk_r: number | null;
}

const props = defineProps<{
  planId: number | null;
  items: PlanItem[];
}>();
const emit = defineEmits<{
  (e: "item-added", item: PlanItem): void;
  (e: "risks-adopted", itemId: number): void;
  (e: "refresh-plan"): void;
  (e: "no-risk-confirmed", payload: { itemId: number; confirmed: boolean }): void;
}>();

const newItem = reactive({ work_name: "", work_description: "", team_label: "" });
const addLoading = ref(false);
const addError = ref("");

const recommendations = ref<Record<number, Recommendation[]>>({});
const selectedRevisions = ref<Record<number, number[]>>({});
const recLoading = ref<Record<number, boolean>>({});
const adoptLoading = ref<Record<number, boolean>>({});
const adoptionStatus = ref<Record<number, boolean>>({});
const itemErrors = ref<Record<number, string>>({});
const showAllRecommendations = ref<Record<number, boolean>>({});
const noRiskOption = ref<Record<number, boolean>>({});
const noRiskConfirmed = ref<Record<number, boolean>>({});
const defaultVisibleCount = 2;

watch(
  () => props.items,
  (items) => {
    for (const item of items) {
      if (selectedRevisions.value[item.id] === undefined) {
        selectedRevisions.value[item.id] = [];
      }
      if (item.risk_refs?.some((r: any) => r.link_type === "ADOPTED" || r.is_selected)) {
        adoptionStatus.value[item.id] = true;
      }
    }
  },
  { immediate: true, deep: true },
);

async function addItem() {
  if (!props.planId) return;
  addLoading.value = true;
  addError.value = "";
  try {
    const res = await api.post(`/daily-work-plans/${props.planId}/items`, {
      work_name: newItem.work_name,
      work_description: newItem.work_description,
      team_label: newItem.team_label || null,
    });
    emit("item-added", res.data);
    newItem.work_name = "";
    newItem.work_description = "";
    newItem.team_label = "";
  } catch (err: any) {
    addError.value = err?.response?.data?.detail ?? "항목 추가에 실패했습니다.";
  } finally {
    addLoading.value = false;
  }
}

async function recommendRisks(itemId: number) {
  recLoading.value[itemId] = true;
  itemErrors.value[itemId] = "";
  try {
    await api.post(`/daily-work-plan-items/${itemId}/recommend-risks`, { top_n: 10 });
    const refsRes = await api.get(`/daily-work-plan-items/${itemId}/risk-refs`);
    const refs: any[] = refsRes.data ?? [];
    if (refs.length === 0) {
      itemErrors.value[itemId] = "매칭되는 위험요인이 없습니다.";
      recommendations.value[itemId] = [];
      noRiskOption.value[itemId] = true;
      noRiskConfirmed.value[itemId] = true;
      emitNoRisk(itemId);
      return;
    }
    noRiskOption.value[itemId] = false;
    noRiskConfirmed.value[itemId] = false;
    emitNoRisk(itemId);
    const recs: Recommendation[] = refs.map((r: any) => ({
      revision_id: r.risk_revision_id,
      risk_factor: r.risk_factor ?? "",
      countermeasure: r.countermeasure ?? "",
      score: r.score ?? null,
      risk_r: r.risk_r ?? null,
    }));
    recommendations.value[itemId] = recs;
    selectedRevisions.value[itemId] = recs.slice(0, defaultVisibleCount).map((r) => r.revision_id);
    showAllRecommendations.value[itemId] = false;
  } catch (err: any) {
    itemErrors.value[itemId] = err?.response?.data?.detail ?? "추천 조회에 실패했습니다.";
  } finally {
    recLoading.value[itemId] = false;
  }
}

async function adoptRisks(itemId: number) {
  const ids = selectedRevisions.value[itemId] ?? [];
  if (ids.length === 0) {
    itemErrors.value[itemId] = "채택할 위험요인을 선택하세요.";
    return;
  }
  adoptLoading.value[itemId] = true;
  itemErrors.value[itemId] = "";
  try {
    await api.post(`/daily-work-plan-items/${itemId}/adopt-risks`, {
      risk_revision_ids: ids,
    });
    adoptionStatus.value[itemId] = true;
    emit("risks-adopted", itemId);
    emit("refresh-plan");
  } catch (err: any) {
    itemErrors.value[itemId] = err?.response?.data?.detail ?? "위험요인 채택에 실패했습니다.";
  } finally {
    adoptLoading.value[itemId] = false;
  }
}

function visibleRecommendations(itemId: number): Recommendation[] {
  const rows = recommendations.value[itemId] ?? [];
  if (showAllRecommendations.value[itemId]) return rows;
  return rows.slice(0, defaultVisibleCount);
}

function toggleShowAll(itemId: number) {
  showAllRecommendations.value[itemId] = !showAllRecommendations.value[itemId];
}

function emitNoRisk(itemId: number) {
  emit("no-risk-confirmed", { itemId, confirmed: !!noRiskConfirmed.value[itemId] });
}
</script>
