<script setup lang="ts">
export interface WorkerListUser {
  id: number;
  login_id: string;
  name: string;
  role: string;
}

defineProps<{
  users: WorkerListUser[];
  selectedUserId: number | null;
  roleLabel: (role: string) => string;
}>();

const emit = defineEmits<{
  select: [userId: number];
}>();
</script>

<template>
  <div class="flex max-h-[70vh] flex-col gap-2 overflow-auto">
    <button
      v-for="user in users"
      :key="user.id"
      type="button"
      class="cursor-pointer rounded-[10px] border border-slate-200 bg-white p-3 text-left transition hover:border-slate-300 hover:shadow-sm"
      :class="selectedUserId === user.id ? 'border-blue-600 shadow-[0_0_0_1px_rgba(37,99,235,0.2)]' : ''"
      @click="emit('select', user.id)"
    >
      <div class="mb-1 font-bold text-slate-900">{{ user.name }}</div>
      <div class="text-xs text-slate-500">{{ user.login_id }} | {{ roleLabel(user.role) }}</div>
    </button>
  </div>
</template>
