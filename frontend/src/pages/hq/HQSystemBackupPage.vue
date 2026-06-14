<template>
  <div class="backup-page">
    <h1 class="page-title">전체 시스템 백업</h1>
    <p class="page-desc">
      DB·업로드 파일·서버 소스(backend, frontend, deploy, scripts, docs)를 하나의 ZIP으로 받습니다.
      다른 서버로 이전·재해 복구 시 <code>RESTORE.md</code>·<code>manifest.json</code>을 참고하세요.
    </p>

    <section class="panel">
      <h2>포함 항목</h2>
      <ul class="include-list">
        <li>SQLite DB (<code>database/besma.db</code>) — 일관 스냅샷</li>
        <li><code>storage/</code> — 제출 문서·이미지 등</li>
        <li><code>backend/</code>, <code>frontend/</code>, <code>deploy/</code>, <code>scripts/</code>, <code>docs/</code></li>
        <li><code>.env</code> (서버에 있을 경우)</li>
        <li>사고 NAS 경로가 설정된 경우 <code>accident_nas/</code></li>
      </ul>
      <p class="note">venv·node_modules 등은 용량 절감을 위해 제외됩니다.</p>
    </section>

    <section class="panel actions-panel">
      <button
        class="stitch-btn-primary backup-btn"
        type="button"
        :disabled="running"
        @click="startBackup"
      >
        {{ running ? progressLabel : "전체 백업 다운로드" }}
      </button>
      <p v-if="lastInfo" class="success">{{ lastInfo }}</p>
      <p v-if="error" class="error">{{ error }}</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { canSystemBackup } from "@/utils/systemBackupAccess";

const auth = useAuthStore();
const router = useRouter();
const running = ref(false);
const progressLabel = ref("백업 생성 중…");
const error = ref("");
const lastInfo = ref("");

const allowed = computed(() => canSystemBackup(auth.user));

onMounted(async () => {
  if (!auth.user) {
    await auth.loadMe();
  }
  if (!allowed.value) {
    await router.replace({ name: "hq-safe-dashboard" });
  }
});

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

async function startBackup() {
  if (!allowed.value || running.value) return;
  running.value = true;
  error.value = "";
  lastInfo.value = "";
  progressLabel.value = "백업 생성 중… (수 분 소요될 수 있습니다)";
  try {
    const prep = await api.post("/system-backup/prepare-download", null, { timeout: 1_800_000 });
    const token = prep.data.download_token as string;
    const filename = (prep.data.filename as string) || "besma-full-backup.zip";
    const fileCount = prep.data.file_count as number;
    const zipBytes = prep.data.zip_bytes as number;

    progressLabel.value = "다운로드 중…";
    const res = await api.get(`/system-backup/download/${encodeURIComponent(token)}`, {
      responseType: "blob",
      timeout: 1_800_000,
    });

    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    lastInfo.value = `백업 완료 — ${fileCount.toLocaleString()}개 파일, ${formatBytes(zipBytes)}`;
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof detail === "string" ? detail : "백업에 실패했습니다. 잠시 후 다시 시도하세요.";
  } finally {
    running.value = false;
    progressLabel.value = "백업 생성 중…";
  }
}
</script>

<style scoped>
.backup-page {
  max-width: 720px;
}

.page-title {
  margin: 0 0 8px;
  font-size: 1.35rem;
}

.page-desc {
  margin: 0 0 20px;
  color: #475569;
  line-height: 1.55;
  font-size: 14px;
}

.panel {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 18px;
  margin-bottom: 16px;
}

.panel h2 {
  margin: 0 0 10px;
  font-size: 1rem;
}

.include-list {
  margin: 0;
  padding-left: 1.2rem;
  line-height: 1.6;
  font-size: 14px;
}

.note {
  margin: 12px 0 0;
  font-size: 13px;
  color: #64748b;
}

.backup-btn {
  min-height: 48px;
  padding: 12px 20px;
  font-size: 15px;
}

.success {
  margin: 12px 0 0;
  color: #166534;
  font-weight: 600;
}

.error {
  margin: 12px 0 0;
  color: #b91c1c;
  font-weight: 600;
}
</style>
