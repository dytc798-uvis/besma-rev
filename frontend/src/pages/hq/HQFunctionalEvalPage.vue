<template>
  <div class="fe-hq-page">
    <div class="page-head">
      <div>
        <h1 class="page-title">기능인 인정제 · 본사</h1>
        <p class="page-sub">
          출역일보 기준 현장별 평가 현황
          <span v-if="period?.last_attendance_date" class="attendance-badge">
            · 출역 {{ period.last_attendance_date }} ({{ period.attendance_row_count }}명)
          </span>
          <span v-if="period" class="attendance-badge">
            · 마감 {{ period.deadline_date }}
            <span :class="period.is_closed ? 'badge closed inline' : 'badge open inline'">{{ period.is_closed ? "마감" : "진행" }}</span>
          </span>
        </p>
      </div>
      <div class="head-actions">
        <button class="stitch-btn-primary" type="button" :disabled="exportingGrade" @click="downloadSiteGradeWorkbook()">
          {{ exportingGrade ? "출력 중..." : "현장별 기능인등급 출력" }}
        </button>
        <button class="stitch-btn-secondary" type="button" :disabled="exporting" @click="downloadEvalExcel">
          {{ exporting ? "다운로드 중..." : "평가 현황(간략)" }}
        </button>
        <button class="stitch-btn-secondary" type="button" @click="loadOverview">새로고침</button>
      </div>
    </div>

    <p v-if="attendanceMessage" class="attendance-warn">{{ attendanceMessage }}</p>
    <p v-if="gapsMissingEvaluator.length" class="attendance-warn gaps-warn">
      출역은 있으나 BESMA 소장 계정이 없는 현장 {{ gapsMissingEvaluator.length }}곳:
      {{ gapsMissingEvaluator.join(", ") }}
    </p>
    <p v-if="loadError" class="load-error">{{ loadError }}</p>

    <!-- 대표·본사용 현황 대시보드 -->
    <section v-if="!selectedSite" class="panel dashboard-panel">
      <div v-if="!activeBucket" class="bucket-grid">
        <button
          type="button"
          class="bucket-card bucket-card--progress"
          @click="selectBucket('in_progress')"
        >
          <span class="bucket-card__label">진행 중 현장</span>
          <span class="bucket-card__count">{{ bucketCounts.in_progress }}</span>
          <span class="bucket-card__hint">평가가 일부 완료된 현장</span>
        </button>
        <button
          type="button"
          class="bucket-card bucket-card--pending"
          @click="selectBucket('not_started')"
        >
          <span class="bucket-card__label">미평가 현장</span>
          <span class="bucket-card__count">{{ bucketCounts.not_started }}</span>
          <span class="bucket-card__hint">아직 평가가 시작되지 않음</span>
        </button>
        <button
          type="button"
          class="bucket-card bucket-card--done"
          @click="selectBucket('completed')"
        >
          <span class="bucket-card__label">완료 현장</span>
          <span class="bucket-card__count">{{ bucketCounts.completed }}</span>
          <span class="bucket-card__hint">전원 평가 완료</span>
        </button>
      </div>

      <div v-else class="bucket-list-panel">
        <div class="bucket-list-head">
          <button type="button" class="stitch-btn-secondary back-btn" @click="clearBucket">← 전체 현황</button>
          <h2>{{ bucketTitle }}</h2>
          <span class="bucket-list-count">{{ bucketSites.length }}곳</span>
        </div>
        <label class="bucket-search">
          검색
          <input v-model="siteSearch" type="text" placeholder="현장명·코드·소장명" class="input-md" />
        </label>
        <ul v-if="bucketSites.length" class="site-list">
          <li v-for="s in filteredBucketSites" :key="s.site_code">
            <button type="button" class="site-list-item" @click="openSite(s)">
              <div class="site-list-item__main">
                <strong>{{ s.site_name }}</strong>
                <span class="site-list-item__meta">{{ s.site_code }} · 소장 {{ s.evaluator_name }}</span>
              </div>
              <div class="site-list-item__progress">
                <span class="progress-pill">{{ s.progress }}</span>
                <div class="progress-bar" aria-hidden="true">
                  <div class="progress-bar__fill" :style="{ width: `${s.progress_pct ?? 0}%` }" />
                </div>
              </div>
              <span class="chevron">›</span>
            </button>
          </li>
        </ul>
        <p v-else class="muted empty-bucket">해당 구분의 현장이 없습니다.</p>
      </div>
    </section>

    <!-- 현장 상세: 소장 평가 화면과 동일한 등급 현황 -->
    <section v-else class="panel site-detail-panel">
      <div class="detail-head">
        <button class="stitch-btn-secondary back-btn" type="button" @click="closeSite">← {{ bucketTitle || "현장 목록" }}</button>
        <div class="detail-head-text">
          <h2>{{ selectedSite.site_name }}</h2>
          <p class="panel-sub">
            {{ selectedSite.site_code }} · 소장 {{ selectedSite.evaluator_name }}
            · 진행 <strong>{{ siteDetail?.site?.progress || selectedSite.progress }}</strong>
            <span v-if="siteApproval?.status_label"> · {{ siteApproval.status_label }}</span>
          </p>
        </div>
        <button class="stitch-btn-secondary" type="button" :disabled="exportingGrade" @click="downloadSiteGradeWorkbook(selectedSite.site_code)">
          {{ exportingGrade ? "출력 중…" : "등급표" }}
        </button>
      </div>
      <div v-if="siteApproval" class="approval-summary">
        <span>평가 완료 {{ siteApproval.site_complete_workers }}/{{ siteApproval.site_total_workers }}명</span>
        <span v-if="siteApproval.team_total"> · 팀원 {{ siteApproval.team_complete }}/{{ siteApproval.team_total }}</span>
        <span v-if="siteApproval.direct_total"> · 직영 {{ siteApproval.direct_complete }}/{{ siteApproval.direct_total }}</span>
      </div>
      <div v-if="loadingSite" class="muted">불러오는 중...</div>
      <div v-else class="table-scroll">
        <table class="data-table roster-like-table">
          <thead>
            <tr>
              <th>성명</th>
              <th>상태</th>
              <th>기능 (2-1)</th>
              <th>안전·제재 (2-2)</th>
              <th>비고</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in evalRows" :key="row.worker_id" :class="row.needs_highlight ? 'row-highlight--alert' : ''">
              <td>{{ row.name }}</td>
              <td><span :class="evalStatusClass(row.eval_status)">{{ row.eval_status_label || "—" }}</span></td>
              <td><span :class="gradeClass(row.functional_grade)">{{ row.functional_grade }}</span></td>
              <td><span :class="gradeClass(row.safety_grade)">{{ row.safety_grade }}</span></td>
              <td class="remark">{{ row.remark }}</td>
            </tr>
            <tr v-if="!evalRows.length">
              <td colspan="5" class="muted">출역 대상 근로자가 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel collapsible ops-panel">
      <button class="section-toggle" type="button" @click="showOps = !showOps">
        {{ showOps ? "▾" : "▸" }} 승인·마감·운영
      </button>
      <template v-if="showOps">
        <div class="row deadline-row">
          <label>
            마감일
            <input v-model="deadlineInput" type="date" />
          </label>
          <button class="stitch-btn-primary" type="button" :disabled="!period" @click="saveDeadline">마감일 저장</button>
          <span v-if="totals" class="kpi">현장 {{ totals.sites }} · 근로자 {{ totals.workers }}명</span>
        </div>

    <div class="evaluator-accounts-panel inner-section">
      <div class="evaluator-accounts-head">
        <div>
          <h2>중간 평가자(팀장) 계정</h2>
          <p class="panel-sub">
            출역 {{ evaluatorAccounts?.split_threshold ?? 10 }}명 초과 현장은 팀장이 팀원을 평가합니다. 소장은 직영 평가 후 현장 전체를 승인합니다.
          </p>
        </div>
        <div class="evaluator-accounts-actions">
          <button class="stitch-btn-secondary" type="button" :disabled="loadingEvaluatorAccounts" @click="loadEvaluatorAccounts">
            {{ loadingEvaluatorAccounts ? "조회 중…" : "계정 목록 조회" }}
          </button>
          <button
            class="stitch-btn-secondary"
            type="button"
            :disabled="!evaluatorAccountItems.length"
            @click="downloadEvaluatorAccountsTxt"
          >
            TXT 다운로드
          </button>
        </div>
      </div>
      <p v-if="evaluatorAccountsSummary" class="meta success">{{ evaluatorAccountsSummary }}</p>
      <div v-if="evaluatorAccountItems.length" class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>현장</th>
              <th>역할</th>
              <th>이름</th>
              <th>로그인 ID</th>
              <th>담당</th>
              <th>분산</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in evaluatorAccountItems" :key="`${row.site_code}-${row.login_id}`">
              <td>{{ row.site_alias || row.site_code }} · {{ row.site_name }}</td>
              <td>{{ row.role }}</td>
              <td>{{ row.name }}</td>
              <td><code>{{ row.login_id }}</code></td>
              <td>{{ row.assigned_worker_count || "—" }}</td>
              <td>{{ row.team_split_active ? "팀장분산" : "소장전원" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="approval-queue-panel inner-section">
      <h2>승인 처리</h2>
      <p class="panel-sub">소장 승인 → 안전보건실 → 대표이사(부현대표-김홍수) 최종 승인 순서입니다.</p>
      <div class="approval-queue-actions">
        <button class="stitch-btn-secondary" type="button" :disabled="loadingHqApprovals" @click="loadHqApprovals">
          {{ loadingHqApprovals ? "조회 중…" : "승인 대기 새로고침" }}
        </button>
      </div>
      <h3>안전보건실 검토 대기 (소장 승인 완료)</h3>
      <div v-if="hqPendingApprovals.length" class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>현장</th>
              <th>완료</th>
              <th>제출</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in hqPendingApprovals" :key="row.site_code">
              <td>{{ row.site_code }}</td>
              <td>{{ row.site_complete_workers }}/{{ row.site_total_workers }}</td>
              <td>{{ row.site_submitted_at || "—" }}</td>
              <td class="actions-inline">
                <button class="stitch-btn-primary" type="button" @click="approveHq(row.site_code)">승인</button>
                <button class="stitch-btn-secondary" type="button" @click="rejectHq(row.site_code)">반려</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted">대기 중인 현장이 없습니다.</p>

      <h3>대표이사 최종 승인 대기</h3>
      <div v-if="ceoPendingApprovals.length" class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>현장</th>
              <th>완료</th>
              <th>본사승인</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in ceoPendingApprovals" :key="row.site_code">
              <td>{{ row.site_code }}</td>
              <td>{{ row.site_complete_workers }}/{{ row.site_total_workers }}</td>
              <td>{{ row.hq_approved_at || "—" }}</td>
              <td class="actions-inline">
                <button class="stitch-btn-primary" type="button" @click="approveCeo(row.site_code)">최종 승인</button>
                <button class="stitch-btn-secondary" type="button" @click="rejectCeo(row.site_code)">반려</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted">대기 중인 현장이 없습니다.</p>
    </div>
      </template>
    </section>

    <section class="panel collapsible">
      <button class="section-toggle" type="button" @click="showAdmin = !showAdmin">
        {{ showAdmin ? "▾" : "▸" }} 명부·제재 관리
      </button>
      <template v-if="showAdmin">
        <h3>① 월별현장별집계 (xls) — 시즌·갱신</h3>
        <p class="panel-sub">
          현장코드·현장명·소장명 → 로그인 ID <code>별칭-이름</code>(예: 대우청라-박명식). 비밀번호는 출역일보 반영 시 주민번호(B열) 앞 6자리로 설정됩니다.
        </p>
        <div class="row import-row">
          <input ref="aggregateInput" type="file" accept=".xlsx,.xls" @change="onAggregateFileChange" />
          <button
            class="stitch-btn-primary"
            type="button"
            :disabled="!aggregateFile || applyingAggregate"
            @click="applySiteAggregate"
          >
            {{ applyingAggregate ? "반영 중..." : "현장집계 반영" }}
          </button>
        </div>
        <p v-if="aggregateResult" class="meta success">{{ aggregateResult }}</p>
        <div v-if="aggregateAccountRows.length" class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>현장코드</th>
                <th>별칭</th>
                <th>소장</th>
                <th>로그인 ID</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in aggregateAccountRows" :key="row.site_code">
                <td>{{ row.site_code }}</td>
                <td>{{ row.site_alias }}</td>
                <td>{{ row.manager_name }}</td>
                <td>{{ row.login_id }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h3>② 출역일보 (ERP xls/xlsx) — 매일 1회</h3>
        <p class="panel-sub">
          ① 반영 후 업로드. 10명 이하 현장은 소장이 전원 평가, 11명 초과는 직영=소장·팀원=팀장 평가 후 소장 전체 승인.
        </p>
        <div class="row import-row">
          <input ref="attendanceInput" type="file" accept=".xlsx,.xls" @change="onAttendanceFileChange" />
          <button
            class="stitch-btn-primary"
            type="button"
            :disabled="!attendanceFile || applyingAttendance"
            @click="applyAttendance"
          >
            {{ applyingAttendance ? "반영 중..." : "출역일보 반영" }}
          </button>
        </div>
        <p v-if="attendanceResult" class="meta success">{{ attendanceResult }}</p>
        <div v-if="attendanceAccountRows.length" class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>현장</th>
                <th>역할</th>
                <th>로그인 ID</th>
                <th>초기 PW</th>
                <th>담당</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in attendanceAccountRows" :key="`${row.login_id}-${idx}`">
                <td>{{ row.site_code }}</td>
                <td>{{ row.role }}</td>
                <td>{{ row.login_id }}</td>
                <td>{{ row.initial_password }}</td>
                <td>{{ row.team_worker_count ?? "—" }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h3>일용직 참조 명부 (xlsx, 선택)</h3>
        <p class="panel-sub">소속현장·소장 계정·주민번호 매핑용 참조 데이터입니다.</p>
        <div class="row import-row">
          <input ref="fileInput" type="file" accept=".xlsx,.xls" @change="onFileChange" />
          <button class="stitch-btn-secondary" type="button" :disabled="!rosterFile || diffing" @click="runDiff">
            {{ diffing ? "DIFF 중..." : "DIFF 미리보기" }}
          </button>
          <button class="stitch-btn-primary" type="button" :disabled="!rosterFile || applying" @click="applyRoster">
            {{ applying ? "반영 중..." : "DIFF 반영" }}
          </button>
          <button class="stitch-btn-secondary" type="button" :disabled="!period?.is_closed" @click="downloadSanctionExcel">
            제재 엑셀 (마감 후)
          </button>
        </div>
        <div v-if="diffResult" class="diff-summary">
          <span>신규 {{ diffResult.new_count }}</span>
          <span>변경 {{ diffResult.updated_count }}</span>
          <span>제외 {{ diffResult.removed_count }}</span>
        </div>
        <p v-if="applyResult" class="meta success">{{ applyResult }}</p>

        <h3>팀장 분산평가 계정 반영 (10명 초과 현장)</h3>
        <p class="panel-sub">
          출역 10명 이하 현장은 소장이 전원 평가합니다. 11명 초과만 팀장 계정(별칭-이름, PW: 주민번호 앞 6자리) 발급·배정(TXT/XLSX 또는 출역 자동 반영).
        </p>
        <div class="row import-row">
          <input ref="teamLeaderInput" type="file" accept=".txt,.xlsx,.xls" @change="onTeamLeaderFileChange" />
          <button
            class="stitch-btn-primary"
            type="button"
            :disabled="!teamLeaderFile || applyingTeamLeaders"
            @click="applyTeamLeaders"
          >
            {{ applyingTeamLeaders ? "반영 중..." : "팀장 계정/배정 반영" }}
          </button>
        </div>
        <p v-if="teamLeaderResult" class="meta success">{{ teamLeaderResult }}</p>
        <div v-if="teamLeaderRows.length" class="table-scroll">
          <table class="data-table">
            <thead>
              <tr>
                <th>현장코드</th>
                <th>팀장명</th>
                <th>아이디</th>
                <th>초기비밀번호</th>
                <th>담당인원</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in teamLeaderRows" :key="`${row.site_code}-${row.login_id}`">
                <td>{{ row.site_code }}</td>
                <td>{{ row.team_leader_name }}</td>
                <td>{{ row.login_id }}</td>
                <td>{{ row.initial_password }}</td>
                <td>{{ row.team_worker_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "@/services/api";

interface Period {
  id: number;
  deadline_date: string;
  is_closed: boolean;
  last_attendance_date?: string | null;
  attendance_row_count?: number;
}

interface Totals {
  sites: number;
  workers: number;
  fully_complete: number;
  incomplete: number;
}

type SiteBucket = "in_progress" | "not_started" | "completed";

interface SiteRow {
  site_code: string;
  site_name: string;
  evaluator_name: string;
  evaluator_missing?: boolean;
  total: number;
  fully_complete: number;
  progress: string;
  progress_pct?: number;
  has_completed: boolean;
  bucket?: SiteBucket;
  bucket_label?: string;
}

interface EvalRow {
  worker_id: number;
  name: string;
  functional_grade: string;
  safety_grade: string;
  remark: string;
  eval_status?: string;
  eval_status_label?: string;
  needs_highlight?: boolean;
}

interface SiteApprovalSummary {
  status_label?: string;
  site_complete_workers?: number;
  site_total_workers?: number;
  team_total?: number;
  team_complete?: number;
  direct_total?: number;
  direct_complete?: number;
}

interface DiffResult {
  new_count: number;
  updated_count: number;
  removed_count: number;
}

interface TeamLeaderRow {
  site_code: string;
  team_leader_name: string;
  login_id: string;
  initial_password: string;
  team_worker_count: number;
}

interface EvaluatorAccountRow {
  site_code: string;
  site_alias: string;
  site_name: string;
  name: string;
  login_id: string;
  role: string;
  assigned_worker_count: number;
  team_split_active: boolean;
}

interface EvaluatorAccountsPayload {
  split_threshold: number;
  last_attendance_date?: string | null;
  manager_count: number;
  team_leader_count: number;
  split_site_count: number;
  items: EvaluatorAccountRow[];
}

const period = ref<Period | null>(null);
const totals = ref<Totals | null>(null);
const sites = ref<SiteRow[]>([]);
const selectedSite = ref<SiteRow | null>(null);
const siteDetail = ref<{ site: SiteRow; approval?: SiteApprovalSummary } | null>(null);
const siteApproval = computed(() => siteDetail.value?.approval ?? null);
const evalRows = ref<EvalRow[]>([]);
const loadingSite = ref(false);
const exporting = ref(false);
const exportingGrade = ref(false);
const deadlineInput = ref("");
const sortBy = ref("progress");
const sortDir = ref("desc");
const siteSearch = ref("");
const loadError = ref("");
const showAdmin = ref(false);
const showOps = ref(false);
const activeBucket = ref<SiteBucket | null>(null);
const bucketCounts = ref({ in_progress: 0, not_started: 0, completed: 0 });
const rosterFile = ref<File | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const diffing = ref(false);
const applying = ref(false);
const diffResult = ref<DiffResult | null>(null);
const applyResult = ref("");
const aggregateFile = ref<File | null>(null);
const aggregateInput = ref<HTMLInputElement | null>(null);
const applyingAggregate = ref(false);
const aggregateResult = ref("");
const aggregateAccountRows = ref<
  { site_code: string; site_alias: string; manager_name: string; login_id: string }[]
>([]);
const attendanceFile = ref<File | null>(null);
const attendanceInput = ref<HTMLInputElement | null>(null);
const applyingAttendance = ref(false);
const attendanceResult = ref("");
const attendanceAccountRows = ref<
  {
    site_code: string;
    role: string;
    login_id: string;
    initial_password: string;
    team_worker_count?: number;
  }[]
>([]);
const attendanceMessage = ref("");
const gapsMissingEvaluator = ref<string[]>([]);
const teamLeaderFile = ref<File | null>(null);
const teamLeaderInput = ref<HTMLInputElement | null>(null);
const applyingTeamLeaders = ref(false);
const teamLeaderResult = ref("");
const teamLeaderRows = ref<TeamLeaderRow[]>([]);
const loadingEvaluatorAccounts = ref(false);
const evaluatorAccounts = ref<EvaluatorAccountsPayload | null>(null);

const evaluatorAccountItems = computed(() => evaluatorAccounts.value?.items ?? []);

const evaluatorAccountsSummary = computed(() => {
  const p = evaluatorAccounts.value;
  if (!p) return "";
  const date = p.last_attendance_date ? ` · 출역 ${p.last_attendance_date}` : "";
  return `소장 ${p.manager_count}명 · 팀장 ${p.team_leader_count}명 · 팀장분산 현장 ${p.split_site_count}곳${date}`;
});

const bucketTitle = computed(() => {
  if (activeBucket.value === "in_progress") return "진행 중 현장";
  if (activeBucket.value === "not_started") return "미평가 현장";
  if (activeBucket.value === "completed") return "완료 현장";
  return "";
});

const bucketSites = computed(() => {
  if (!activeBucket.value) return [];
  return sites.value.filter((s) => (s.bucket || inferBucket(s)) === activeBucket.value);
});

const filteredBucketSites = computed(() => {
  const q = siteSearch.value.trim().toLowerCase();
  if (!q) return bucketSites.value;
  return bucketSites.value.filter(
    (s) =>
      s.site_code.toLowerCase().includes(q) ||
      (s.site_name || "").toLowerCase().includes(q) ||
      (s.evaluator_name || "").toLowerCase().includes(q),
  );
});

function inferBucket(s: SiteRow): SiteBucket {
  const total = s.total ?? 0;
  const done = s.fully_complete ?? 0;
  if (total <= 0) return "not_started";
  if (done >= total) return "completed";
  if (done <= 0) return "not_started";
  return "in_progress";
}

function selectBucket(bucket: SiteBucket) {
  activeBucket.value = bucket;
  siteSearch.value = "";
}

function clearBucket() {
  activeBucket.value = null;
  siteSearch.value = "";
}

function evalStatusClass(status?: string) {
  if (status === "completed") return "eval-status eval-status--done";
  if (status === "in_progress") return "eval-status eval-status--progress";
  return "eval-status eval-status--pending";
}

function gradeClass(grade: string) {
  if (grade === "미평가") return "grade pending";
  if (grade === "S" || grade === "우수") return "grade s";
  if (grade === "A") return "grade a";
  if (grade === "B" || grade === "보통") return "grade b";
  if (grade === "C" || grade === "D" || grade === "부족" || grade === "최하") return "grade c";
  return "grade done";
}

const loadingHqApprovals = ref(false);
const hqPendingApprovals = ref<Record<string, unknown>[]>([]);
const ceoPendingApprovals = ref<Record<string, unknown>[]>([]);

async function loadHqApprovals() {
  loadingHqApprovals.value = true;
  try {
    const [hqRes, ceoRes] = await Promise.all([
      api.get("/functional-eval/hq/approvals/pending"),
      api.get("/functional-eval/hq/ceo-approvals/pending"),
    ]);
    hqPendingApprovals.value = hqRes.data.items || [];
    ceoPendingApprovals.value = ceoRes.data.items || [];
  } catch {
    hqPendingApprovals.value = [];
    ceoPendingApprovals.value = [];
  } finally {
    loadingHqApprovals.value = false;
  }
}

async function approveHq(siteCode: string) {
  if (!window.confirm(`${siteCode} 현장을 안전보건실에서 승인하시겠습니까?`)) return;
  await api.post(`/functional-eval/hq/approvals/${siteCode}/approve`);
  await loadHqApprovals();
}

async function rejectHq(siteCode: string) {
  const note = window.prompt("반려 사유 (선택)") || "";
  await api.post(`/functional-eval/hq/approvals/${siteCode}/reject`, { note });
  await loadHqApprovals();
}

async function approveCeo(siteCode: string) {
  if (!window.confirm(`${siteCode} 현장을 대표이사 최종 승인하시겠습니까?`)) return;
  await api.post(`/functional-eval/hq/ceo-approvals/${siteCode}/approve`);
  await loadHqApprovals();
}

async function rejectCeo(siteCode: string) {
  const note = window.prompt("반려 사유 (선택)") || "";
  await api.post(`/functional-eval/hq/ceo-approvals/${siteCode}/reject`, { note });
  await loadHqApprovals();
}

async function loadEvaluatorAccounts() {
  loadingEvaluatorAccounts.value = true;
  try {
    const res = await api.get("/functional-eval/hq/evaluator-accounts");
    evaluatorAccounts.value = res.data;
  } catch {
    evaluatorAccounts.value = null;
    loadError.value = "평가자 계정 목록을 불러오지 못했습니다.";
  } finally {
    loadingEvaluatorAccounts.value = false;
  }
}

function downloadEvaluatorAccountsTxt() {
  const items = evaluatorAccountItems.value;
  if (!items.length) return;
  const lines = [
    "현장코드\t별칭\t현장명\t역할\t이름\t로그인ID\t담당인원",
    ...items.map(
      (r) =>
        `${r.site_code}\t${r.site_alias}\t${r.site_name}\t${r.role}\t${r.name}\t${r.login_id}\t${r.assigned_worker_count}`,
    ),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `기능인제_평가자계정_${new Date().toISOString().slice(0, 10)}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

async function loadOverview() {
  loadError.value = "";
  try {
    const res = await api.get("/functional-eval/hq/summary", {
      params: { sort_by: sortBy.value, sort_dir: sortDir.value },
    });
    period.value = res.data.period;
    totals.value = res.data.totals || null;
    attendanceMessage.value = res.data.attendance_message || "";
    const rows = res.data.sites ?? res.data.site_progress ?? [];
    sites.value = Array.isArray(rows) ? rows : [];
    const buckets = res.data.site_buckets;
    if (buckets) {
      bucketCounts.value = {
        in_progress: buckets.in_progress ?? 0,
        not_started: buckets.not_started ?? 0,
        completed: buckets.completed ?? 0,
      };
    } else {
      bucketCounts.value = {
        in_progress: sites.value.filter((s) => inferBucket(s) === "in_progress").length,
        not_started: sites.value.filter((s) => inferBucket(s) === "not_started").length,
        completed: sites.value.filter((s) => inferBucket(s) === "completed").length,
      };
    }
    gapsMissingEvaluator.value = res.data.gaps?.sites_missing_evaluator_account ?? [];
    if (!sites.value.length && (totals.value?.workers ?? 0) > 0) {
      loadError.value = "현장 목록을 불러오지 못했습니다. 새로고침(Ctrl+F5) 후 다시 시도해 주세요.";
    }
    deadlineInput.value = period.value?.deadline_date || "";
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status;
    if (status === 403) {
      loadError.value = "이 계정은 본사 평가 조회 권한이 없습니다. 관리자에게 문의하세요.";
    } else {
      loadError.value = "평가 현황을 불러오지 못했습니다. 네트워크 확인 후 새로고침해 주세요.";
    }
    sites.value = [];
  }
}

async function openSite(site: SiteRow) {
  selectedSite.value = site;
  if (!activeBucket.value && site.bucket) {
    activeBucket.value = site.bucket;
  }
  loadingSite.value = true;
  evalRows.value = [];
  try {
    const res = await api.get(`/functional-eval/hq/sites/${encodeURIComponent(site.site_code)}/evaluations`, {
      params: { sort_by: "name", sort_dir: "asc" },
    });
    siteDetail.value = res.data;
    evalRows.value = res.data.eval_rows || [];
  } finally {
    loadingSite.value = false;
  }
}

function closeSite() {
  selectedSite.value = null;
  siteDetail.value = null;
  evalRows.value = [];
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  rosterFile.value = input.files?.[0] || null;
  diffResult.value = null;
  applyResult.value = "";
}

function onAggregateFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  aggregateFile.value = input.files?.[0] || null;
  aggregateResult.value = "";
  aggregateAccountRows.value = [];
}

function onAttendanceFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  attendanceFile.value = input.files?.[0] || null;
  attendanceResult.value = "";
  attendanceAccountRows.value = [];
}

async function applySiteAggregate() {
  if (!aggregateFile.value) return;
  applyingAggregate.value = true;
  aggregateResult.value = "";
  try {
    const form = new FormData();
    form.append("file", aggregateFile.value);
    const res = await api.post("/functional-eval/hq/site-aggregate/apply", form);
    period.value = res.data.period;
    aggregateAccountRows.value = Array.isArray(res.data.account_rows) ? res.data.account_rows : [];
    aggregateResult.value = `현장 ${res.data.site_count}곳 — 신규 ${res.data.sites_added ?? 0} · 변경 ${res.data.sites_updated ?? 0} · 유지 ${res.data.sites_unchanged ?? 0}`;
    await loadOverview();
  } catch {
    aggregateResult.value = "월별현장별집계 반영에 실패했습니다. 파일 형식을 확인하세요.";
  } finally {
    applyingAggregate.value = false;
  }
}

function onTeamLeaderFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  teamLeaderFile.value = input.files?.[0] || null;
  teamLeaderResult.value = "";
  teamLeaderRows.value = [];
}

async function applyAttendance() {
  if (!attendanceFile.value) return;
  applyingAttendance.value = true;
  attendanceResult.value = "";
  try {
    const form = new FormData();
    form.append("file", attendanceFile.value);
    const res = await api.post("/functional-eval/hq/attendance/apply", form);
    period.value = res.data.period;
    attendanceAccountRows.value = Array.isArray(res.data.account_rows) ? res.data.account_rows : [];
    const skipped = res.data.skipped_no_registry ?? res.data.skipped_no_roster ?? 0;
    const diff = `추가 ${res.data.diff_added ?? 0} · 변경 ${res.data.diff_updated ?? 0} · 유지 ${res.data.diff_unchanged ?? 0} · 제외 ${res.data.diff_removed ?? 0}`;
    attendanceResult.value = `출역일 ${res.data.work_date} · 반영 ${res.data.linked_workers}명 (${diff}) · 계정 ${res.data.created_accounts ?? 0}건 (집계 미매칭 ${skipped}명)`;
    await loadOverview();
  } catch {
    attendanceResult.value = "출역일보 반영에 실패했습니다. 파일 형식을 확인하세요.";
  } finally {
    applyingAttendance.value = false;
  }
}

async function applyTeamLeaders() {
  if (!teamLeaderFile.value) return;
  applyingTeamLeaders.value = true;
  teamLeaderResult.value = "";
  try {
    const form = new FormData();
    form.append("file", teamLeaderFile.value);
    const res = await api.post("/functional-eval/hq/team-leaders/apply", form);
    teamLeaderRows.value = Array.isArray(res.data.account_rows) ? res.data.account_rows : [];
    teamLeaderResult.value = `계정 생성 ${res.data.created_accounts}건 · 팀원 배정 ${res.data.assigned_workers}건`;
    teamLeaderFile.value = null;
    if (teamLeaderInput.value) teamLeaderInput.value.value = "";
    await loadOverview();
  } catch {
    teamLeaderResult.value = "팀장 계정/배정 반영에 실패했습니다. 파일 형식을 확인하세요.";
  } finally {
    applyingTeamLeaders.value = false;
  }
}

async function uploadFile(endpoint: string) {
  const form = new FormData();
  form.append("file", rosterFile.value!);
  return api.post(endpoint, form);
}

async function runDiff() {
  if (!rosterFile.value) return;
  diffing.value = true;
  try {
    const res = await uploadFile("/functional-eval/hq/roster/diff");
    diffResult.value = res.data;
    period.value = res.data.period;
    deadlineInput.value = period.value?.deadline_date || "";
  } finally {
    diffing.value = false;
  }
}

async function applyRoster() {
  if (!rosterFile.value) return;
  applying.value = true;
  try {
    const res = await uploadFile("/functional-eval/hq/roster/apply");
    applyResult.value = `반영 완료 — 신규 ${res.data.new_count}, 변경 ${res.data.updated_count}`;
    rosterFile.value = null;
    if (fileInput.value) fileInput.value.value = "";
    await loadOverview();
    if (selectedSite.value) await openSite(selectedSite.value);
  } finally {
    applying.value = false;
  }
}

async function saveDeadline() {
  if (!period.value || !deadlineInput.value) return;
  await api.patch(`/functional-eval/period/${period.value.id}/deadline`, {
    deadline_date: deadlineInput.value,
  });
  await loadOverview();
}

async function downloadSiteGradeWorkbook(siteCode?: string) {
  exportingGrade.value = true;
  try {
    const res = await api.get("/functional-eval/hq/export/site-grade-workbook", {
      responseType: "blob",
      params: siteCode ? { site_code: siteCode } : undefined,
    });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = siteGradeWorkbookFilename();
    a.click();
    URL.revokeObjectURL(url);
  } finally {
    exportingGrade.value = false;
  }
}

function siteGradeWorkbookFilename() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `현장별 기능인등급-${y}${m}${day}.xlsx`;
}

async function downloadEvalExcel() {
  exporting.value = true;
  try {
    const res = await api.get("/functional-eval/hq/export/evaluations", { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = "functional_eval_grades.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  } finally {
    exporting.value = false;
  }
}

async function downloadSanctionExcel() {
  const res = await api.get("/functional-eval/hq/export", { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = "functional_eval_sanctions.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}

onMounted(async () => {
  await loadOverview();
  await loadHqApprovals();
});
</script>

<style scoped>
.approval-queue-panel h3 { margin: 16px 0 8px; font-size: 14px; }
.approval-queue-actions { margin-bottom: 10px; }
.actions-inline { display: flex; gap: 6px; flex-wrap: wrap; }
.evaluator-accounts-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.evaluator-accounts-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.fe-hq-page { display: flex; flex-direction: column; gap: 16px; }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.head-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px; }
.panel-sub { color: #64748b; font-size: 13px; margin: 4px 0 12px; }
.row { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; margin-top: 8px; }
.toolbar { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; align-items: flex-end; }
.toolbar label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.input-md { min-width: 200px; padding: 6px 8px; border: 1px solid #cbd5e1; border-radius: 6px; }
.kpi { font-size: 13px; color: #475569; margin-left: 8px; }
.table-scroll { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th, .data-table td { border-bottom: 1px solid #e5e7eb; padding: 10px 8px; text-align: left; }
.site-row { cursor: pointer; }
.site-row:hover { background: #f8fafc; }
.site-row--active .progress-pill { font-weight: 600; }
.chevron { color: #94a3b8; width: 24px; text-align: right; }
.progress-pill { font-variant-numeric: tabular-nums; }
.progress-pill.done { color: #166534; }
.detail-head { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 12px; }
.back-btn { flex-shrink: 0; }
.empty-msg { color: #64748b; font-size: 14px; padding: 12px 0; }
.grade { font-weight: 600; font-size: 13px; }
.grade.pending { color: #94a3b8; font-weight: 400; }
.grade.s { color: #166534; }
.grade.a { color: #15803d; }
.grade.b { color: #1d4ed8; }
.grade.c { color: #b45309; }
.grade.d { color: #991b1b; }
.remark { font-size: 13px; color: #475569; }
.badge { padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.badge.open { background: #dcfce7; color: #166534; }
.badge.closed { background: #fee2e2; color: #991b1b; }
.meta.success { color: #166534; font-size: 13px; }
.muted { color: #94a3b8; }
.section-toggle { width: 100%; text-align: left; background: none; border: none; font-size: 15px; font-weight: 600; cursor: pointer; padding: 0 0 12px; }
.diff-summary { display: flex; gap: 12px; margin-top: 8px; font-size: 14px; }
.attendance-warn {
  color: #9a3412;
  background: #fff7ed;
  border: 1px solid #fdba74;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 14px;
  margin-bottom: 8px;
}
.gaps-warn { font-size: 13px; }
.tag-missing {
  display: inline-block;
  margin-left: 4px;
  color: #b45309;
  font-weight: 700;
}
.load-error { color: #991b1b; background: #fef2f2; padding: 10px 12px; border-radius: 8px; font-size: 14px; margin-bottom: 8px; }
.data-table tbody tr.row-highlight--alert { background: #fef2f2; }
.data-table tbody tr.row-highlight--alert:hover { background: #fee2e2; }
.dashboard-panel { padding: 20px; }
.bucket-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
@media (max-width: 900px) {
  .bucket-grid { grid-template-columns: 1fr; }
}
.bucket-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 20px 18px;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: box-shadow 0.15s, border-color 0.15s, transform 0.15s;
}
.bucket-card:hover {
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}
.bucket-card--progress { border-top: 4px solid #2563eb; }
.bucket-card--pending { border-top: 4px solid #ea580c; }
.bucket-card--done { border-top: 4px solid #16a34a; }
.bucket-card__label { font-size: 15px; font-weight: 600; color: #0f172a; }
.bucket-card__count { font-size: 36px; font-weight: 700; line-height: 1; color: #0f172a; font-variant-numeric: tabular-nums; }
.bucket-card__hint { font-size: 13px; color: #64748b; }
.bucket-list-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.bucket-list-head h2 { margin: 0; font-size: 18px; }
.bucket-list-count { font-size: 14px; color: #64748b; }
.bucket-search { display: flex; flex-direction: column; gap: 4px; font-size: 13px; margin-bottom: 12px; }
.site-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.site-list-item {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 12px;
  align-items: center;
  padding: 14px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  text-align: left;
}
.site-list-item:hover { background: #f8fafc; border-color: #cbd5e1; }
.site-list-item__main { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.site-list-item__main strong { font-size: 15px; color: #0f172a; }
.site-list-item__meta { font-size: 13px; color: #64748b; }
.site-list-item__progress { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; min-width: 88px; }
.progress-bar { width: 88px; height: 6px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
.progress-bar__fill { height: 100%; background: #2563eb; border-radius: 999px; }
.site-detail-panel .detail-head-text { flex: 1; min-width: 0; }
.approval-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 14px;
  color: #334155;
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 8px;
}
.eval-status { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 999px; }
.eval-status--done { background: #dcfce7; color: #166534; }
.eval-status--progress { background: #dbeafe; color: #1d4ed8; }
.eval-status--pending { background: #f1f5f9; color: #64748b; }
.ops-panel .inner-section { margin-top: 16px; padding-top: 12px; border-top: 1px solid #e5e7eb; }
.deadline-row { margin-bottom: 8px; }
.badge.inline { margin-left: 4px; vertical-align: middle; }
.empty-bucket { padding: 24px 0; text-align: center; }
</style>
