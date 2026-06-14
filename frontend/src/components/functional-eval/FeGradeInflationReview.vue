<template>
  <section class="fe-grade-review">
    <h3 class="fe-grade-review__title">기능/품질 등급 분포 검토 (2-1)</h3>
    <p class="fe-grade-review__hint">{{ functionalGuide }}</p>
    <p class="fe-grade-review__note muted">
      안전(2-2) 평가는 감점형으로 별도 운영하며, S등급 20% 제한·C등급 비율 강제는 적용하지 않습니다.
    </p>

    <table v-if="snapshot" class="fe-grade-review__table">
      <tbody>
        <tr>
          <th>총 평가대상</th>
          <td>{{ snapshot.workers_total }}명 (평가완료 {{ snapshot.evaluated_total }}명)</td>
        </tr>
        <tr v-for="g in gradeOrder" :key="g">
          <th>{{ g }}등급</th>
          <td>{{ gradeCount(g) }}명 · {{ gradePct(g) }}%</td>
        </tr>
      </tbody>
    </table>

    <div v-if="review?.s_over_limit" class="fe-grade-review__warn">
      <p>현재 기능/품질 S등급 비율이 권장 기준 20%를 초과했습니다. 우수등급 초과 부여 사유를 입력해 주세요.</p>
      <label class="fe-grade-review__label">
        <span>S등급 초과 사유 (필수, 10자 이상)</span>
        <textarea
          :value="sReason"
          rows="3"
          class="fe-sign-textarea"
          placeholder="예: 해당 현장은 숙련공 비중이 높고, 무재해·품질우수 실적이 확인되어 S등급 비율이 높습니다."
          @input="emit('update:sReason', ($event.target as HTMLTextAreaElement).value)"
        />
      </label>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { FE_FUNCTIONAL_EVAL_GUIDE } from "@/config/feEvalPolicyText";

export type GradeInflationReview = {
  grade_distribution_snapshot?: {
    workers_total?: number;
    evaluated_total?: number;
    s_count?: number;
    c_count?: number;
    s_ratio?: number;
    grades?: Record<string, { count: number; pct: number }>;
  };
  s_over_limit?: boolean;
  no_c_grade?: boolean;
};

const props = defineProps<{
  review: GradeInflationReview | null;
  sReason: string;
}>();

const emit = defineEmits<{
  (e: "update:sReason", value: string): void;
}>();

const functionalGuide = FE_FUNCTIONAL_EVAL_GUIDE;
const gradeOrder = ["S", "A", "B", "C"] as const;
const snapshot = computed(() => props.review?.grade_distribution_snapshot ?? null);

function gradeCount(code: string) {
  return snapshot.value?.grades?.[code]?.count ?? 0;
}

function gradePct(code: string) {
  return snapshot.value?.grades?.[code]?.pct ?? 0;
}
</script>

<style scoped>
.fe-grade-review {
  margin-bottom: 14px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}
.fe-grade-review__title {
  margin: 0 0 6px;
  font-size: 15px;
}
.fe-grade-review__hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: #334155;
  line-height: 1.45;
}
.fe-grade-review__note {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.4;
}
.muted {
  color: #64748b;
}
.fe-grade-review__table {
  width: 100%;
  font-size: 13px;
  border-collapse: collapse;
  margin-bottom: 10px;
}
.fe-grade-review__table th {
  text-align: left;
  padding: 4px 8px 4px 0;
  color: #475569;
  font-weight: 600;
  width: 88px;
}
.fe-grade-review__table td {
  padding: 4px 0;
}
.fe-grade-review__warn {
  margin-top: 10px;
  padding: 10px;
  border-radius: 8px;
  background: #fff7ed;
  border: 1px solid #fdba74;
}
.fe-grade-review__warn p {
  margin: 0 0 8px;
  font-size: 13px;
  color: #9a3412;
  font-weight: 600;
}
.fe-grade-review__label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #334155;
}
</style>
