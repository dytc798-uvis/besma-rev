<template>
  <div class="nsd-site-page">
    <header class="nsd-head">
      <h1>신규현장 배포 현황</h1>
      <p v-if="item && !item.is_complete" class="nsd-warn">
        사인물 부착 사진과 필요 서류를 모두 등록하면 강조 표시가 해제됩니다.
      </p>
      <p v-else-if="item?.is_complete" class="nsd-done">배포·서류 등록이 완료되었습니다.</p>
    </header>

    <p v-if="loading" class="muted">불러오는 중…</p>
    <p v-else-if="!item" class="empty-msg">이 현장에 연결된 신규 배포 항목이 없습니다.</p>

    <template v-else>
      <section class="panel">
        <h2>{{ item.site_name }}</h2>
        <p class="muted">{{ item.site_code }} · {{ item.site_alias }}</p>
        <div v-for="sg in item.safety_items" :key="sg.key" class="upload-block">
          <h3>{{ sg.label }} — 부착 사진</h3>
          <p v-if="item.photos[sg.key]" class="file-meta">
            등록됨: {{ item.photos[sg.key].original_filename }}
            <a href="#" @click.prevent="openFile(item.photos[sg.key].download_url)">보기</a>
          </p>
          <input type="file" accept="image/*" @change="onPhotoFile(sg.key, $event)" />
        </div>
      </section>

      <section class="panel">
        <h2>필요 서류</h2>
        <div v-for="doc in item.required_documents" :key="doc.key" class="upload-block">
          <h3>{{ doc.label }}</h3>
          <p v-if="item.documents[doc.key]" class="file-meta">
            등록됨: {{ item.documents[doc.key].original_filename }}
            <a href="#" @click.prevent="openFile(item.documents[doc.key].download_url)">보기</a>
          </p>
          <input type="file" accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx" @change="onDocFile(doc.key, $event)" />
        </div>
      </section>
      <p v-if="uploadError" class="error">{{ uploadError }}</p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "@/services/api";

interface FileMeta {
  id: number;
  original_filename: string;
  download_url: string;
}

interface DeploymentDetail {
  id: number;
  site_name: string;
  site_code?: string;
  site_alias: string;
  is_complete: boolean;
  safety_items: { key: string; label: string }[];
  required_documents: { key: string; label: string }[];
  photos: Record<string, FileMeta>;
  documents: Record<string, FileMeta>;
}

const item = ref<DeploymentDetail | null>(null);
const loading = ref(true);
const uploadError = ref("");

function photoUrl(meta: FileMeta) {
  return meta.download_url;
}

async function openFile(path: string) {
  const res = await api.get(path, { responseType: "blob" });
  const blobUrl = URL.createObjectURL(res.data);
  window.open(blobUrl, "_blank", "noopener");
}

async function load() {
  loading.value = true;
  try {
    const res = await api.get("/new-site-deployment/my-site");
    item.value = res.data.item;
    window.dispatchEvent(new CustomEvent("besma-nsd-updated"));
  } finally {
    loading.value = false;
  }
}

async function onPhotoFile(itemKey: string, e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || !item.value) return;
  uploadError.value = "";
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await api.post(`/new-site-deployment/deployments/${item.value.id}/photos/${itemKey}`, form);
    item.value = res.data;
    window.dispatchEvent(new CustomEvent("besma-nsd-updated"));
  } catch {
    uploadError.value = "사진 업로드에 실패했습니다.";
  } finally {
    input.value = "";
  }
}

async function onDocFile(docType: string, e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || !item.value) return;
  uploadError.value = "";
  const form = new FormData();
  form.append("file", file);
  try {
    const res = await api.post(`/new-site-deployment/deployments/${item.value.id}/documents/${docType}`, form);
    item.value = res.data;
    window.dispatchEvent(new CustomEvent("besma-nsd-updated"));
  } catch {
    uploadError.value = "서류 업로드에 실패했습니다.";
  } finally {
    input.value = "";
  }
}

onMounted(load);
</script>

<style scoped>
.nsd-site-page { max-width: 720px; }
.nsd-warn { background: #fff7ed; border: 1px solid #fdba74; padding: 10px 12px; border-radius: 8px; }
.nsd-done { color: #166534; background: #dcfce7; padding: 10px 12px; border-radius: 8px; }
.upload-block { margin: 16px 0; padding-bottom: 12px; border-bottom: 1px solid #e2e8f0; }
.upload-block h3 { margin: 0 0 8px; font-size: 15px; }
.file-meta { font-size: 13px; color: #475569; }
</style>
