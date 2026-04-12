<script setup lang="ts">
import BaseTable from "../BaseTable.vue";
import StatusBadge from "../StatusBadge.vue";

export interface DocumentRegistryItem {
  site_id: number;
  requirement_id: number;
  title: string;
  frequency: string;
  status: string;
  review_note: string | null;
  latest_document_id: number | null;
  latest_uploaded_at: string | null;
  category?: string | null;
  section?: string | null;
}

defineProps<{
  items: DocumentRegistryItem[];
  statusLabel: (status: string) => string;
  statusBadgeTone: (status: string) => "success" | "warn" | "danger" | "neutral" | "info";
  formatDateTime: (value: string | null) => string;
  categoryLabel?: (category: string | null | undefined) => string;
}>();

const emit = defineEmits<{
  startReview: [documentId: number];
  approve: [documentId: number];
  openReject: [documentId: number];
  goDetail: [documentId: number];
}>();
</script>

<template>
  <BaseTable>
    <thead>
      <tr>
        <th>문서명</th>
        <th>구분</th>
        <th>주기</th>
        <th>상태</th>
        <th>최근 제출일</th>
        <th>코멘트</th>
        <th>액션</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="item in items" :key="`${item.site_id}-${item.requirement_id}`">
        <td>
          <strong>{{ item.title }}</strong>
        </td>
        <td>{{ categoryLabel ? categoryLabel(item.category) : item.category || "-" }}</td>
        <td>{{ item.frequency }}</td>
        <td>
          <StatusBadge :tone="statusBadgeTone(item.status)">{{ statusLabel(item.status) }}</StatusBadge>
        </td>
        <td>{{ formatDateTime(item.latest_uploaded_at) }}</td>
        <td class="max-w-[220px] text-[13px] text-slate-500">{{ item.review_note || "—" }}</td>
        <td>
          <div class="flex flex-wrap gap-2">
            <button
              v-if="item.latest_document_id && (item.status === 'SUBMITTED' || item.status === 'IN_REVIEW')"
              type="button"
              class="stitch-btn-primary px-3 py-1.5 text-xs"
              @click="emit('approve', item.latest_document_id!)"
            >
              승인
            </button>
            <button
              v-if="item.latest_document_id && (item.status === 'SUBMITTED' || item.status === 'IN_REVIEW')"
              type="button"
              class="stitch-btn-secondary px-3 py-1.5 text-xs"
              @click="emit('openReject', item.latest_document_id!)"
            >
              반려
            </button>
            <button
              v-if="item.latest_document_id"
              type="button"
              class="stitch-btn-secondary px-3 py-1.5 text-xs"
              @click="emit('goDetail', item.latest_document_id!)"
            >
              보기
            </button>
          </div>
        </td>
      </tr>
      <tr v-if="items.length === 0">
        <td colspan="7" class="!py-8 text-center text-slate-500">선택한 현장의 문서가 없습니다.</td>
      </tr>
    </tbody>
  </BaseTable>
</template>
