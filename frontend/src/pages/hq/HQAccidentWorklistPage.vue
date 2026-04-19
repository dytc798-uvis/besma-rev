<template>
  <div class="card">
    <div class="head-row">
      <div>
        <div class="card-title">사고 작업리스트</div>
        <p class="muted">HQ가 우선 처리해야 할 사고를 파싱상태·첨부 누락 기준으로 모아봅니다.</p>
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
      <section v-for="section in primarySections" :key="section.key" class="sec">
        <div class="sec-head">
          <h3 class="sec-title">{{ section.title }}</h3>
          <span class="count-badge">{{ section.data.count }}건</span>
        </div>
        <table class="basic-table">
          <thead>
            <tr>
              <th>사고ID</th>
              <th>사고일시</th>
              <th>현장명</th>
              <th>성명</th>
              <th>파싱</th>
              <th>첨부</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in section.data.items" :key="`${section.key}-${row.id}`" class="click-row" @click="goDetail(row.id)">
              <td>{{ row.accident_id }}</td>
              <td>{{ formatDt(row.accident_datetime || row.accident_datetime_text || row.created_at) }}</td>
              <td>{{ row.site_standard_name || row.site_name || "—" }}</td>
              <td>{{ row.injured_person_name || "—" }}</td>
              <td>{{ row.parse_status }}</td>
              <td>{{ row.has_attachments ? "Y" : "N" }}</td>
            </tr>
            <tr v-if="section.data.items.length === 0">
              <td colspan="6" class="empty">대상 건이 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </section>

      <details class="maintenance-block">
        <summary class="maintenance-summary">
          <span class="maintenance-title">partial / 비success 건 (점검용)</span>
          <span class="count-badge count-badge-muted">{{ worklist.parse_review.count }}건</span>
        </summary>
        <p class="maintenance-hint">
          자동 파싱이 완전하지 않은 건입니다. 여유 있을 때 펼쳐 확인·수정하면 됩니다.
        </p>
        <table class="basic-table">
          <thead>
            <tr>
              <th>사고ID</th>
              <th>사고일시</th>
              <th>현장명</th>
              <th>성명</th>
              <th>파싱</th>
              <th>첨부</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in worklist.parse_review.items"
              :key="`parse_review-${row.id}`"
              class="click-row"
              @click="goDetail(row.id)"
            >
              <td>{{ row.accident_id }}</td>
              <td>{{ formatDt(row.accident_datetime || row.accident_datetime_text || row.created_at) }}</td>
              <td>{{ row.site_standard_name || row.site_name || "—" }}</td>
              <td>{{ row.injured_person_name || "—" }}</td>
              <td>{{ row.parse_status }}</td>
              <td>{{ row.has_attachments ? "Y" : "N" }}</td>
            </tr>
            <tr v-if="worklist.parse_review.items.length === 0">
              <td colspan="6" class="empty">대상 건이 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </details>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { fetchAccidentWorklist, type AccidentWorklistResponse } from "@/services/accidents";

const router = useRouter();
const loading = ref(false);
const errorMessage = ref("");
const worklist = ref<AccidentWorklistResponse | null>(null);
const storedPreferWorklist = localStorage.getItem("besma_accident_prefer_worklist");
const preferWorklist = ref(storedPreferWorklist == null ? true : storedPreferWorklist === "true");

const primarySections = computed(() => {
  if (!worklist.value) return [];
  return [
    { key: "missing_attachments", title: "첨부 없는 건", data: worklist.value.missing_attachments },
    { key: "recent", title: "최근 등록 건", data: worklist.value.recent },
  ];
});

function formatDt(value: string) {
  try {
    return new Date(value).toLocaleString("ko-KR");
  } catch {
    return value;
  }
}

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
.count-badge-muted {
  background: #f1f5f9;
  color: #64748b;
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
.maintenance-block {
  margin-top: 28px;
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}
.maintenance-summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 600;
  color: #475569;
}
.maintenance-summary::-webkit-details-marker {
  display: none;
}
.maintenance-title {
  flex: 1;
  text-align: left;
}
.maintenance-hint {
  margin: 10px 0 12px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
}
</style>
