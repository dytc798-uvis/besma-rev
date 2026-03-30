<script setup lang="ts">
import BaseTable from "../BaseTable.vue";

defineProps<{
  rows: Array<{
    work_description: string | null;
    risk_factor: string;
    counterplan: string;
  }>;
}>();
</script>

<template>
  <BaseTable>
    <thead>
      <tr>
        <th>작업내용</th>
        <th>위험요인</th>
        <th>대책</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(row, idx) in rows" :key="idx">
        <td>{{ row.work_description || "—" }}</td>
        <td>{{ row.risk_factor }}</td>
        <td>{{ row.counterplan }}</td>
      </tr>
    </tbody>
  </BaseTable>
</template>
