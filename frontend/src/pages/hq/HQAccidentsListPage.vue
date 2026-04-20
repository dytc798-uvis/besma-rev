<template>
  <div class="card">
    <div class="head-row">
      <div>
        <div class="card-title">사고관리</div>
        <p class="muted">기본 목록은 자동 파싱이 success가 아닌 건만 보여줍니다. 전체 보기에서 모든 사고를 확인할 수 있습니다.</p>
      </div>
      <div class="toolbar-actions">
        <RouterLink class="secondary-link" to="/hq-safe/accidents/worklist">작업리스트</RouterLink>
        <button type="button" class="secondary" :disabled="syncingExcel" @click="syncExcel">
          {{ syncingExcel ? "동기화 중…" : "엑셀 동기화" }}
        </button>
        <button type="button" class="secondary" @click="downloadExcel">엑셀 다운로드</button>
        <button type="button" class="secondary" @click="load">새로고침</button>
        <RouterLink class="primary-link" to="/hq-safe/accidents/new">사고 등록</RouterLink>
      </div>
    </div>

    <div class="filter-row">
      <label class="show-all">
        <input v-model="showAll" type="checkbox" @change="load" />
        <span>전체 보기</span>
      </label>
      <label class="show-all">
        <input v-model="preferWorklist" type="checkbox" @change="persistWorklistPreference" />
        <span>첫 진입 시 작업리스트 우선</span>
      </label>
      <span class="summary-pill">현재 {{ items.length }}건</span>
    </div>

    <table class="basic-table">
      <thead>
        <tr>
          <th>사고ID</th>
          <th>사고일</th>
          <th>현장명</th>
          <th>성명</th>
          <th>상태</th>
          <th>관리구분</th>
          <th>첨부</th>
          <th>NAS 링크</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="row.id" class="click-row" @click="goDetail(row.id)">
          <td>{{ row.accident_id }}</td>
          <td>{{ formatAccidentDateForListRow(row.accident_datetime, row.accident_datetime_text, row.created_at) }}</td>
          <td>{{ row.site_standard_name || row.site_name || "—" }}</td>
          <td>{{ row.injured_person_name || "—" }}</td>
          <td>{{ row.status }}</td>
          <td>{{ row.management_category }}</td>
          <td>{{ row.has_attachments ? "Y" : "N" }}</td>
          <td>
            <button type="button" class="linkish" @click.stop="openNasLauncher(row.id)">탐색기</button>
          </td>
        </tr>
        <tr v-if="!loading && items.length === 0">
          <td colspan="8" class="empty">표시할 사고가 없습니다.</td>
        </tr>
      </tbody>
    </table>
    <p v-if="loading" class="muted">불러오는 중…</p>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { api } from "@/services/api";
import {
  downloadAccidentNasFolderLauncher,
  fetchAccidents,
  syncAccidentsToMasterExcel,
  type AccidentListItem,
} from "@/services/accidents";
import { formatAccidentDateForListRow } from "@/utils/accidentDateDisplay";

const router = useRouter();
const items = ref<AccidentListItem[]>([]);
const loading = ref(false);
const syncingExcel = ref(false);
const errorMessage = ref("");
const showAll = ref(false);
const storedPreferWorklist = localStorage.getItem("besma_accident_prefer_worklist");
const preferWorklist = ref(storedPreferWorklist == null ? true : storedPreferWorklist === "true");

function persistWorklistPreference() {
  localStorage.setItem("besma_accident_prefer_worklist", String(preferWorklist.value));
}

async function load() {
  errorMessage.value = "";
  loading.value = true;
  try {
    items.value = await fetchAccidents({
      show_all: showAll.value,
    });
  } catch {
    errorMessage.value = "사고관리 목록을 불러오지 못했습니다.";
    items.value = [];
  } finally {
    loading.value = false;
  }
}

function goDetail(id: number) {
  router.push({ name: "hq-safe-accident-detail", params: { id: String(id) } });
}

async function openNasLauncher(accidentPk: number) {
  try {
    await downloadAccidentNasFolderLauncher(accidentPk);
    window.alert(
      "탐색기를 여는 실행 파일을 내려받았습니다.\n\n다운로드 폴더의 .bat 파일을 더블클릭하면 해당 NAS 폴더가 열립니다.",
    );
  } catch {
    window.alert("탐색기 열기 파일을 받지 못했습니다.");
  }
}

async function downloadExcel() {
  try {
    const res = await api.get("/accidents/export/master", { responseType: "blob" });
    const blob = new Blob([res.data], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "BESMA_사고MASTER_export.xlsx";
    a.click();
    window.URL.revokeObjectURL(url);
  } catch {
    window.alert("엑셀 다운로드에 실패했습니다.");
  }
}

async function syncExcel() {
  const ok = window.confirm("기존 엑셀 파일을 덮어씁니다. 진행하시겠습니까?");
  if (!ok) return;
  syncingExcel.value = true;
  try {
    await syncAccidentsToMasterExcel();
    window.alert("엑셀 반영 완료");
  } catch {
    window.alert("엑셀 동기화에 실패했습니다.");
  } finally {
    syncingExcel.value = false;
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
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 12px;
}
.muted {
  color: #64748b;
  font-size: 13px;
  margin: 8px 0 12px;
}
.toolbar-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.filter-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.show-all,
.summary-pill {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  padding: 6px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  font-size: 13px;
}
.primary-link {
  display: inline-block;
  padding: 6px 12px;
  background: #2563eb;
  color: #fff;
  border-radius: 6px;
  text-decoration: none;
  font-size: 14px;
}
.secondary-link {
  display: inline-block;
  padding: 6px 12px;
  border: 1px solid #cbd5e1;
  color: #334155;
  border-radius: 6px;
  text-decoration: none;
  font-size: 14px;
}
.click-row {
  cursor: pointer;
}
.click-row:hover {
  background: #f1f5f9;
}
.linkish {
  color: #2563eb;
  background: transparent;
  border: 0;
  cursor: pointer;
}
.empty {
  text-align: center;
  color: #64748b;
}
.error {
  margin-top: 10px;
  color: #b91c1c;
  font-weight: 600;
}
</style>
