<template>
  <div class="card">
    <div class="card-title">{{ menu?.title || "동적 메뉴" }}</div>
    <p class="guide">본사 설정에서 만든 사용자 정의 메뉴입니다.</p>

    <section v-if="menu?.menu_type === 'BOARD'">
      <div class="write-box">
        <input v-model="boardForm.title" type="text" placeholder="제목" />
        <textarea v-model="boardForm.body" rows="3" placeholder="내용" />
        <button class="primary" @click="createBoardPost">등록</button>
      </div>
      <ul class="post-list">
        <li v-for="post in boardPosts" :key="post.id" class="post-item">
          <div class="post-title">{{ post.title }}</div>
          <p class="post-body">{{ post.body }}</p>
          <small class="meta">{{ post.created_by_name || "-" }}</small>
          <div class="comment-list">
            <p v-for="c in post.comments" :key="c.id">- {{ c.body }} ({{ c.created_by_name || "-" }})</p>
          </div>
          <div class="comment-write">
            <input v-model="commentDrafts[post.id]" type="text" placeholder="댓글" />
            <button class="secondary" @click="createBoardComment(post.id)">등록</button>
          </div>
        </li>
      </ul>
    </section>

    <section v-else-if="menu?.menu_type === 'TABLE'">
      <table class="basic-table">
        <thead>
          <tr>
            <th v-for="col in tableColumns" :key="col.key">{{ col.label }}</th>
            <th>액션</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td v-for="col in tableColumns" :key="`new-${col.key}`">
              <input v-model="newRow[col.key]" type="text" />
            </td>
            <td><button class="primary" @click="createTableRow">추가</button></td>
          </tr>
          <tr v-for="row in tableRows" :key="row.id">
            <td v-for="col in tableColumns" :key="`${row.id}-${col.key}`">
              <input v-model="row.row_data[col.key]" type="text" />
            </td>
            <td class="actions">
              <button class="secondary" @click="saveTableRow(row)">저장</button>
              <button class="secondary danger" @click="deleteTableRow(row.id)">삭제</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { api } from "@/services/api";

const route = useRoute();
const slug = computed(() => String(route.params.slug || ""));
const menu = ref<any | null>(null);
const boardPosts = ref<any[]>([]);
const tableRows = ref<any[]>([]);
const boardForm = ref({ title: "", body: "" });
const commentDrafts = ref<Record<number, string>>({});
const newRow = ref<Record<string, string>>({});

const tableColumns = computed(() => {
  const cols = menu.value?.custom_config?.columns;
  return Array.isArray(cols) && cols.length > 0
    ? cols
    : [{ key: "col1", label: "컬럼1" }, { key: "col2", label: "컬럼2" }];
});

async function load() {
  if (!slug.value) return;
  const detail = await api.get(`/dynamic-menus/${slug.value}`);
  menu.value = detail.data?.menu;
  if (menu.value?.menu_type === "BOARD") {
    const posts = await api.get(`/dynamic-menus/${slug.value}/board-posts`);
    boardPosts.value = posts.data?.items ?? [];
  } else if (menu.value?.menu_type === "TABLE") {
    const rows = await api.get(`/dynamic-menus/${slug.value}/table-rows`);
    tableRows.value = rows.data?.items ?? [];
    newRow.value = Object.fromEntries(tableColumns.value.map((c: any) => [c.key, ""]));
  }
}

async function createBoardPost() {
  if (!boardForm.value.title.trim() || !boardForm.value.body.trim()) return;
  await api.post(`/dynamic-menus/${slug.value}/board-posts`, {
    title: boardForm.value.title.trim(),
    body: boardForm.value.body.trim(),
  });
  boardForm.value = { title: "", body: "" };
  await load();
}

async function createBoardComment(postId: number) {
  const body = (commentDrafts.value[postId] || "").trim();
  if (!body) return;
  await api.post(`/dynamic-menus/${slug.value}/board-posts/${postId}/comments`, { body });
  commentDrafts.value[postId] = "";
  await load();
}

async function createTableRow() {
  await api.post(`/dynamic-menus/${slug.value}/table-rows`, { row_data: newRow.value });
  newRow.value = Object.fromEntries(tableColumns.value.map((c: any) => [c.key, ""]));
  await load();
}

async function saveTableRow(row: any) {
  await api.put(`/dynamic-menus/${slug.value}/table-rows/${row.id}`, { row_data: row.row_data });
  await load();
}

async function deleteTableRow(rowId: number) {
  await api.delete(`/dynamic-menus/${slug.value}/table-rows/${rowId}`);
  await load();
}

onMounted(load);
</script>

