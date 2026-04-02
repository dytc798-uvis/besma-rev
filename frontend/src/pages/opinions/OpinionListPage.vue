<template>
  <div class="card">
    <div class="card-title">운영 아이디어 제안</div>
    <div class="toolbar">
      <div class="toolbar-filters">
        <select v-model="statusFilter">
          <option value="">전체 상태</option>
          <option value="RECEIVED">접수</option>
          <option value="REVIEWING">검토중</option>
          <option value="ACTIONED">조치완료</option>
          <option value="HOLD">보류</option>
        </select>
        <input v-model="keyword" type="text" placeholder="키워드" />
      </div>
      <div class="toolbar-actions">
        <button class="secondary" @click="load">조회</button>
        <button class="primary" @click="openNew">새 아이디어 등록</button>
      </div>
    </div>
    <table class="basic-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>이름</th>
          <th>아이디어</th>
          <th>상태</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="op in opinions"
          :key="op.id"
          @click="goDetail(op.id)"
          style="cursor: pointer"
        >
          <td>{{ op.id }}</td>
          <td>{{ op.reporter_type || "-" }}</td>
          <td>{{ op.content }}</td>
          <td>{{ op.status }}</td>
        </tr>
        <tr v-if="opinions.length === 0">
          <td colspan="4" style="text-align: center; color: #6b7280">데이터가 없습니다.</td>
        </tr>
      </tbody>
    </table>

    <div v-if="showNew" style="margin-top: 16px">
      <h3 style="font-size: 14px; margin-bottom: 8px">운영 아이디어 등록</h3>
      <form class="form-grid" @submit.prevent="createOpinion">
        <div class="form-field">
          <label>이름</label>
          <input v-model="newReporterType" type="text" placeholder="자유 입력" required />
        </div>
        <div class="form-field" style="grid-column: span 2">
          <label>아이디어</label>
          <textarea v-model="newContent" rows="3" placeholder="운영 개선 아이디어를 입력하세요" required />
        </div>
        <div style="grid-column: span 2; display: flex; justify-content: flex-end; gap: 8px">
          <button type="button" class="secondary" @click="showNew = false">취소</button>
          <button type="submit" class="primary">등록</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";

interface OpinionItem {
  id: number;
  reporter_type: string;
  content: string;
  status: string;
}

const opinions = ref<OpinionItem[]>([]);
const statusFilter = ref("");
const keyword = ref("");
const showNew = ref(false);
const newCategory = ref("운영 아이디어");
const newReporterType = ref("현장");
const newContent = ref("");

const router = useRouter();

async function load() {
  const res = await api.get("/opinions", {
    params: {
      status_filter: statusFilter.value || undefined,
      keyword: keyword.value || undefined,
    },
  });
  opinions.value = res.data;
}

function goDetail(id: number) {
  router.push({ name: "hq-safe-opinion-detail", params: { id } }).catch(() => {
    router.push({ name: "site-opinion-detail", params: { id } });
  });
}

function openNew() {
  showNew.value = true;
}

async function createOpinion() {
  await api.post("/opinions", {
    site_id: null,
    category: newCategory.value,
    content: newContent.value,
    reporter_type: newReporterType.value,
  });
  showNew.value = false;
  newCategory.value = "운영 아이디어";
  newReporterType.value = "현장";
  newContent.value = "";
  await load();
}

onMounted(load);
</script>

