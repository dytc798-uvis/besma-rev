<template>
  <div class="policy-page">
    <BaseCard title="안전보건 방침 및 목표">
      <template #actions>
        <button class="secondary" @click="load">새로고침</button>
      </template>

      <div class="view-toggle" v-if="isSiteUi">
        <button class="secondary" :class="{ active: viewScope === 'SITE' }" @click="switchScope('SITE')">현장 방침/목표</button>
        <button class="secondary" :class="{ active: viewScope === 'HQ' }" @click="switchScope('HQ')">본사 방침/목표</button>
      </div>

      <div class="panel-grid">
        <section class="panel-card">
          <h3>방침</h3>
          <p class="title">{{ payload.policy?.title || "등록된 방침이 없습니다." }}</p>
          <p class="meta">{{ formatDateTime(payload.policy?.uploaded_at) }}</p>
          <a v-if="payload.policy?.file_url" :href="resolveFileUrl(payload.policy.file_url)" target="_blank" rel="noopener">파일 보기</a>
          <div v-if="isHqUi" class="upload-box">
            <input v-model="hqPolicyTitle" type="text" placeholder="본사 방침 제목" />
            <input type="file" @change="onFileChange($event, 'policy')" />
            <button class="primary" :disabled="!hqPolicyFile || !hqPolicyTitle.trim() || uploading" @click="uploadHq('POLICY')">
              업로드
            </button>
          </div>
        </section>

        <section class="panel-card">
          <h3>목표</h3>
          <p class="title">{{ payload.target?.title || "등록된 목표가 없습니다." }}</p>
          <p class="meta">{{ formatDateTime(payload.target?.uploaded_at) }}</p>
          <a v-if="payload.target?.file_url" :href="resolveFileUrl(payload.target.file_url)" target="_blank" rel="noopener">파일 보기</a>
          <div v-if="isHqUi" class="upload-box">
            <input v-model="hqTargetTitle" type="text" placeholder="본사 목표 제목" />
            <input type="file" @change="onFileChange($event, 'target')" />
            <button class="primary" :disabled="!hqTargetFile || !hqTargetTitle.trim() || uploading" @click="uploadHq('TARGET')">
              업로드
            </button>
          </div>
        </section>
      </div>
    </BaseCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { BaseCard } from "@/components/product";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";

interface UploadedDoc {
  title: string;
  uploaded_at: string;
  file_url: string;
}

const auth = useAuthStore();
const viewScope = ref<"SITE" | "HQ">("SITE");
const payload = ref<{ policy: UploadedDoc | null; target: UploadedDoc | null }>({ policy: null, target: null });
const hqPolicyTitle = ref("");
const hqTargetTitle = ref("");
const hqPolicyFile = ref<File | null>(null);
const hqTargetFile = ref<File | null>(null);
const uploading = ref(false);

const isSiteUi = computed(() => auth.user?.ui_type === "SITE");
const isHqUi = computed(() => auth.user?.ui_type === "HQ_SAFE");

function formatDateTime(value: string | null | undefined) {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(dt);
}

function resolveFileUrl(path: string) {
  return `${api.defaults.baseURL}${path}`;
}

function onFileChange(event: Event, key: "policy" | "target") {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0] ?? null;
  if (key === "policy") hqPolicyFile.value = file;
  else hqTargetFile.value = file;
}

function switchScope(scope: "SITE" | "HQ") {
  viewScope.value = scope;
  void load();
}

async function load() {
  const params: Record<string, unknown> = { scope: viewScope.value };
  if (viewScope.value === "SITE" && auth.user?.site_id) {
    params.site_id = auth.user.site_id;
  }
  const res = await api.get("/safety-policy-goals/view", { params });
  payload.value = { policy: res.data.policy, target: res.data.target };
}

async function uploadHq(kind: "POLICY" | "TARGET") {
  const file = kind === "POLICY" ? hqPolicyFile.value : hqTargetFile.value;
  const title = kind === "POLICY" ? hqPolicyTitle.value : hqTargetTitle.value;
  if (!file || !title.trim()) return;
  uploading.value = true;
  try {
    const form = new FormData();
    form.append("scope", "HQ");
    form.append("kind", kind);
    form.append("title", title.trim());
    form.append("file", file);
    await api.post("/safety-policy-goals/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    if (kind === "POLICY") {
      hqPolicyFile.value = null;
      hqPolicyTitle.value = "";
    } else {
      hqTargetFile.value = null;
      hqTargetTitle.value = "";
    }
    viewScope.value = "HQ";
    await load();
  } finally {
    uploading.value = false;
  }
}

onMounted(() => {
  viewScope.value = isSiteUi.value ? "SITE" : "HQ";
  void load();
});
</script>

<style scoped>
.view-toggle { display: flex; gap: 8px; margin-bottom: 12px; }
.view-toggle .active { background: #0f172a; color: #fff; }
.panel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.panel-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
.title { font-weight: 700; margin: 0; }
.meta { margin: 0; color: #64748b; font-size: 12px; }
.upload-box { margin-top: 8px; display: flex; flex-direction: column; gap: 8px; }
@media (max-width: 920px) { .panel-grid { grid-template-columns: 1fr; } }
</style>
