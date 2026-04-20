<template>
  <div class="card">
    <div class="head-row">
      <div>
        <div class="card-title">사고 작업리스트</div>
        <p class="muted">최근 등록된 사고를 빠르게 열람·처리합니다. 파싱 상태 등은 상세 화면에서 확인할 수 있습니다.</p>
      </div>
      <div class="head-actions">
        <label class="prefer-toggle">
          <input v-model="preferWorklist" type="checkbox" @change="persistWorklistPreference" />
          <span>첫 진입 시 작업리스트 우선</span>
        </label>
        <RouterLink class="secondary-link" :to="{ name: 'hq-safe-accidents', query: { bypassWorklist: '1' } }">사고관리 목록</RouterLink>
      </div>
    </div>

    <div v-if="loading" class="muted">불러오는 중…</div>
    <p v-else-if="errorMessage" class="error">{{ errorMessage }}</p>

    <template v-else-if="worklist">
      <section class="sec">
        <div class="sec-head">
          <h3 class="sec-title">최근 등록 건</h3>
          <span class="count-badge">{{ worklist.recent.count }}건</span>
        </div>
        <table class="basic-table">
          <thead>
            <tr>
              <th>사고ID</th>
              <th>사고일</th>
              <th>현장명</th>
              <th>성명</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in worklist.recent.items"
              :key="`recent-${row.id}`"
              class="click-row"
              @click="goDetail(row.id)"
            >
              <td>{{ row.accident_id }}</td>
              <td>{{ formatAccidentDateForListRow(row.accident_datetime, row.accident_datetime_text, row.created_at) }}</td>
              <td>{{ row.site_standard_name || row.site_name || "—" }}</td>
              <td>{{ row.injured_person_name || "—" }}</td>
            </tr>
            <tr v-if="worklist.recent.items.length === 0">
              <td colspan="4" class="empty">대상 건이 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { fetchAccidentWorklist, type AccidentWorklistResponse } from "@/services/accidents";
import { formatAccidentDateForListRow } from "@/utils/accidentDateDisplay";

const router = useRouter();
const loading = ref(false);
const errorMessage = ref("");
const worklist = ref<AccidentWorklistResponse | null>(null);
const storedPreferWorklist = localStorage.getItem("besma_accident_prefer_worklist");
const preferWorklist = ref(storedPreferWorklist == null ? true : storedPreferWorklist === "true");

function persistWorklistPreference() {
  localStorage.setItem("besma_accident_prefer_worklist", String(preferWorklist.value));
}

function goDetail(id: number) {
  router.push({ name: "hq-safe-accident-detail", params: { id: String(id) } });
}

async function load() {
  loading.value = true;
  errorMessage.value = "";
  try {
    worklist.value = await fetchAccidentWorklist();
  } catch {
    errorMessage.value = "작업리스트를 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  persistWorklistPreference();
  void load();
});
</script>

<style scoped>
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.muted {
  color: #64748b;
  font-size: 13px;
}
.prefer-toggle {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  font-size: 13px;
  color: #475569;
}
.secondary-link {
  color: #334155;
  text-decoration: none;
  padding: 6px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 14px;
}
.sec {
  margin-top: 20px;
}
.sec-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.sec-title {
  margin: 0;
  font-size: 16px;
}
.count-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
}
.click-row {
  cursor: pointer;
}
.click-row:hover {
  background: #f8fafc;
}
.empty {
  text-align: center;
  color: #64748b;
}
.error {
  margin-top: 12px;
  color: #b91c1c;
  font-weight: 600;
}
</style>
