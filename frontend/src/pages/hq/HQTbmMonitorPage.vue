<template>
  <div class="tbm-page">
    <header class="page-head">
      <div>
        <h1 class="page-title">TBM 모니터</h1>
        <p class="page-sub">문서 선택 후 참가자·위험요인 요약 (API)</p>
      </div>
    </header>

    <WorkCard title="문서 선택">
      <template #actions>
        <button type="button" class="stitch-btn-secondary" @click="loadDocuments">문서 새로고침</button>
        <button type="button" class="stitch-btn-primary" :disabled="!documentId" @click="loadSummary">TBM 요약 조회</button>
      </template>
      <div class="toolbar-row">
        <label class="field-label">document_id</label>
        <input v-model.number="documentId" type="text" class="field-input" placeholder="document_id 입력" />
      </div>
      <p v-if="message" class="monitor-message">{{ message }}</p>
    </WorkCard>

    <section v-if="summary" class="stitch-kpi-grid kpi-tight">
      <KpiCard
        label="교육 인원"
        :value="summary.education_count"
        accent="blue"
        :progress-pct="rosterProgressPct"
        footer-note="명단 대비 응답 비율"
        badge-text="교육"
        badge-tone="info"
      />
      <KpiCard
        label="시작 서명 완료"
        :value="startedCount"
        accent="orange"
        :progress-pct="startedProgressPct"
        :footer-note="`대상 대비 ${startedProgressPct}%`"
        :badge-text="startedCount >= summary.education_count && summary.education_count > 0 ? '완료' : '진행'"
        :badge-tone="startedCount >= summary.education_count && summary.education_count > 0 ? 'success' : 'warn'"
      />
      <KpiCard
        label="종료 서명 완료"
        :value="completedCount"
        accent="slate"
        :progress-pct="completedProgressPct"
        :footer-note="`대상 대비 ${completedProgressPct}%`"
        badge-text="종료"
        badge-tone="neutral"
      />
      <KpiCard
        label="ISSUE 인원"
        :value="issueCount"
        accent="red"
        :progress-pct="issueProgressPct"
        footer-note="이슈 플래그 인원"
        :badge-text="issueCount > 0 ? '확인' : '없음'"
        :badge-tone="issueCount > 0 ? 'danger' : 'success'"
      />
    </section>

    <WorkCard v-if="summary" title="문서 액션" subtitle="선택된 TBM 문서">
      <template #actions>
        <button type="button" class="stitch-btn-primary" @click="goTbmView">TBM 보기</button>
        <button type="button" class="stitch-btn-secondary" @click="goDocumentDetail">문서 상세</button>
      </template>
      <p class="doc-ref">document #{{ summary.document_id }}</p>
    </WorkCard>

    <WorkCard v-if="summary" title="참가자 서명 현황">
      <BaseTable>
        <thead>
          <tr>
            <th>근로자</th>
            <th>ack_status</th>
            <th>시작서명</th>
            <th>종료서명</th>
            <th>end_status</th>
            <th>issue</th>
            <th>개인증빙</th>
            <th>시작 이미지</th>
            <th>종료 이미지</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in summary.participants" :key="p.person_id">
            <td>
              <strong>{{ p.name }}</strong>
            </td>
            <td>
              <StatusBadge :tone="ackTone(p.ack_status)">{{ p.ack_status }}</StatusBadge>
            </td>
            <td>{{ p.start_signed_at || "—" }}</td>
            <td>{{ p.end_signed_at || "—" }}</td>
            <td>
              <StatusBadge v-if="p.end_status" tone="neutral">{{ p.end_status }}</StatusBadge>
              <span v-else>—</span>
            </td>
            <td>
              <StatusBadge :tone="p.issue_flag ? 'danger' : 'neutral'">
                {{ p.issue_flag ? "Y" : "N" }}
              </StatusBadge>
            </td>
            <td>
              <button type="button" class="stitch-btn-secondary btn-compact" @click="goSafetyRecord(p.person_id)">
                보기
              </button>
            </td>
            <td>
              <img
                v-if="p.start_signature_data"
                :src="p.start_signature_data"
                alt="start-sign"
                class="sign-thumb"
              />
              <span v-else>—</span>
            </td>
            <td>
              <img v-if="p.end_signature_data" :src="p.end_signature_data" alt="end-sign" class="sign-thumb" />
              <span v-else>—</span>
            </td>
          </tr>
        </tbody>
      </BaseTable>
    </WorkCard>

    <WorkCard v-if="summary?.table_rows?.length" title="TBM 작업 / 위험요인 / 대책">
      <RiskTable :rows="summary.table_rows" />
    </WorkCard>

    <WorkCard title="최근 문서" subtitle="상위 30건">
      <BaseTable>
        <thead>
          <tr>
            <th>ID</th>
            <th>제목</th>
            <th>상태</th>
            <th>액션</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in documents" :key="d.id">
            <td>{{ d.id }}</td>
            <td>
              <strong>{{ d.title }}</strong>
            </td>
            <td>
              <StatusBadge :tone="docStatusTone(d.current_status)">{{ d.current_status }}</StatusBadge>
            </td>
            <td>
              <button type="button" class="stitch-btn-secondary btn-compact" @click="pickDocument(d.id)">선택</button>
            </td>
          </tr>
          <tr v-if="documents.length === 0">
            <td colspan="4" class="empty-cell">문서가 없습니다.</td>
          </tr>
        </tbody>
      </BaseTable>
    </WorkCard>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/services/api";
import { BaseTable, KpiCard, RiskTable, StatusBadge, WorkCard } from "@/components/product";

interface DocItem {
  id: number;
  title: string;
  current_status: string;
}

interface Participant {
  person_id: number;
  name: string;
  ack_status: string;
  start_signed_at: string | null;
  end_signed_at: string | null;
  end_status: string | null;
  issue_flag: boolean;
  start_signature_data?: string | null;
  end_signature_data?: string | null;
}

interface Summary {
  document_id: number;
  education_count: number;
  participants: Participant[];
  table_rows?: Array<{
    work_description: string | null;
    risk_factor: string;
    counterplan: string;
  }>;
}

const router = useRouter();
const documentId = ref<number | null>(null);
const documents = ref<DocItem[]>([]);
const summary = ref<Summary | null>(null);
const message = ref("");

const startedCount = computed(() => summary.value?.participants.filter((p) => !!p.start_signed_at).length ?? 0);
const completedCount = computed(() => summary.value?.participants.filter((p) => !!p.end_signed_at).length ?? 0);
const issueCount = computed(() => summary.value?.participants.filter((p) => p.issue_flag).length ?? 0);

const participantBase = computed(() => Math.max(1, summary.value?.participants.length ?? 1));

const rosterProgressPct = computed(() => {
  const ec = summary.value?.education_count ?? 0;
  if (ec <= 0) return 0;
  const n = summary.value?.participants.length ?? 0;
  return Math.min(100, Math.round((n / ec) * 100));
});

const startedProgressPct = computed(() => {
  const ec = summary.value?.education_count ?? 0;
  if (ec <= 0) return 0;
  return Math.min(100, Math.round((startedCount.value / ec) * 100));
});

const completedProgressPct = computed(() => {
  const ec = summary.value?.education_count ?? 0;
  if (ec <= 0) return 0;
  return Math.min(100, Math.round((completedCount.value / ec) * 100));
});

const issueProgressPct = computed(() =>
  Math.min(100, Math.round((issueCount.value / participantBase.value) * 100)),
);

function ackTone(ack: string): "success" | "warn" | "neutral" {
  const u = (ack || "").toUpperCase();
  if (u.includes("ACK") || u === "COMPLETED" || u === "OK") return "success";
  if (u.includes("PEND") || u.includes("WAIT")) return "warn";
  return "neutral";
}

function docStatusTone(status: string): "success" | "warn" | "danger" | "neutral" | "info" {
  const u = (status || "").toUpperCase();
  if (u.includes("APPROV") || u.includes("DONE") || u.includes("COMPLETE")) return "success";
  if (u.includes("REJECT")) return "danger";
  if (u.includes("PEND") || u.includes("REVIEW") || u.includes("DRAFT")) return "warn";
  return "neutral";
}

async function loadDocuments() {
  const res = await api.get("/documents");
  documents.value = (res.data as DocItem[]).slice(0, 30);
}

async function loadSummary() {
  if (!documentId.value) return;
  message.value = "";
  try {
    const res = await api.get(`/documents/${documentId.value}/tbm-summary`);
    summary.value = res.data;
  } catch (err: unknown) {
    const e = err as { response?: { data?: { detail?: string } } };
    message.value = e?.response?.data?.detail ?? "TBM 요약 조회 실패";
  }
}

function pickDocument(id: number) {
  documentId.value = id;
  loadSummary();
}

function goTbmView() {
  if (!documentId.value) return;
  router.push({ name: "hq-safe-document-tbm-view", params: { id: documentId.value } });
}

function goDocumentDetail() {
  if (!documentId.value) return;
  router.push({ name: "hq-safe-document-detail", params: { id: documentId.value } });
}

function goSafetyRecord(personId: number) {
  router.push({ name: "hq-safe-worker-safety-record", params: { personId } });
}

onMounted(loadDocuments);
</script>

<style scoped>
.tbm-page {
  width: 100%;
  max-width: none;
}

.page-head {
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.page-sub {
  margin: 6px 0 0;
  font-size: 14px;
  color: #64748b;
}

.kpi-tight {
  margin-bottom: 20px;
}

.toolbar-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.field-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.field-input {
  min-width: 200px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
}

.monitor-message {
  color: #dc2626;
  font-size: 14px;
  margin: 8px 0 0;
}

.doc-ref {
  margin: 0;
  font-size: 13px;
  color: #64748b;
}

.sign-thumb {
  width: 120px;
  max-height: 48px;
  object-fit: contain;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
}

.btn-compact {
  padding: 6px 12px;
  font-size: 12px;
}

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 28px !important;
}

</style>
