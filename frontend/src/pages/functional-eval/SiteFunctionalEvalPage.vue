<template>
  <div class="fe-page" :class="{ 'fe-page--team-leader': isTeamLeaderFlow }">
    <nav v-if="isTeamLeaderFlow" class="team-leader-stepbar" aria-label="팀장 업무 단계">
      <span class="team-step team-step--done">① 동의서</span>
      <span
        class="team-step"
        :class="{
          'team-step--active': teamLeaderPhase === 'evaluate',
          'team-step--done': teamLeaderPhase === 'report' || teamLeaderPhase === 'results',
        }"
      >② 팀원 평가</span>
      <span
        class="team-step"
        :class="{
          'team-step--active': teamLeaderPhase === 'report',
          'team-step--done': teamLeaderPhase === 'results',
        }"
      >③ 보고서 서명</span>
      <span class="team-step" :class="{ 'team-step--active': teamLeaderPhase === 'results' }">④ 팀 결과</span>
    </nav>

    <div class="page-head" :class="{ 'page-head--mobile': isMobileViewport }">
      <div class="page-head-text">
        <h1 v-if="!isMobileViewport" class="page-title">기능인 인정제 평가</h1>
        <p class="page-sub">
          <span v-if="evaluator" :class="['evaluator-badge', evaluatorBadgeClass]">{{ evaluatorHeadline }}</span>
          마감일 <strong>{{ period?.deadline_date || "—" }}</strong>
          <span v-if="period?.last_attendance_date"> · 출역 {{ period.last_attendance_date }} ({{ workers.length }}명)</span>
        <button
          v-if="!period?.is_closed"
          class="incomplete-count"
          type="button"
          :disabled="!canStartFromIncomplete"
          @click="startEvaluationFromIncomplete"
        >
          미완료 {{ incompleteCount }}명
        </button>
          <span v-if="period?.is_closed" class="badge closed">마감</span>
          <span v-else class="badge open">진행</span>
        </p>
        <p v-if="period?.is_closed" class="attendance-warn post-period-hint">
          평가 마감 — <strong>포상·제재 이력만</strong> 등록할 수 있습니다. 본사에서 월 2회 검토·승인 후 점수에 반영됩니다.
        </p>
        <p v-if="evaluatorHint" class="evaluator-hint">{{ evaluatorHint }}</p>
        <p v-if="attendanceMessage" class="attendance-warn">{{ attendanceMessage }}</p>
        <p v-if="error && mainView === 'roster'" class="load-error">{{ error }}</p>
      </div>
      <div class="page-head-actions" :class="{ 'page-head-actions--mobile': isMobileViewport }">
      <button
        v-if="!evaluator || isManager"
        class="btn-export stitch-btn-primary"
        type="button"
        :disabled="exportingGrade"
        @click="downloadSiteGradeWorkbook"
      >
        {{ exportingGrade ? "출력 중…" : isMobileViewport ? "등급 출력" : "현장별 기능인등급 출력" }}
      </button>
      <button class="btn-refresh stitch-btn-secondary" type="button" @click="load">새로고침</button>
      </div>
    </div>

        <nav class="fe-tabs" aria-label="기능인 인정제 평가">
      <template v-if="mainView === 'evaluate'">
        <button
          v-if="!isTeamLeaderFlow"
          type="button"
          class="fe-tab fe-tab-back"
          @click="goToRoster"
        >
          ← 현황
        </button>
        <button
          v-else-if="teamLeaderPhase === 'report'"
          type="button"
          class="fe-tab fe-tab-back"
          @click="goToRoster"
        >
          ← 보고서
        </button>
        <button type="button" class="fe-tab" :class="{ active: activeTab === 'functional' }" @click="activeTab = 'functional'">
          2-1 기능
        </button>
        <button type="button" class="fe-tab" :class="{ active: activeTab === 'safety' }" @click="activeTab = 'safety'">
          2-2 안전·제재
        </button>
      </template>
      <template v-else-if="!isTeamLeaderFlow">
        <button type="button" class="fe-tab active">
          등급 현황
        </button>
      </template>
      <template v-else-if="teamLeaderPhase === 'report'">
        <button type="button" class="fe-tab active">③ 평가완료보고서</button>
      </template>
      <template v-else-if="teamLeaderPhase === 'results'">
        <button type="button" class="fe-tab active">④ 팀 평가 결과</button>
      </template>
    </nav>

    <p v-if="saveNotice" class="save-notice" role="status">{{ saveNotice }}</p>

    <!-- 첫 화면: 근로자별 현재 등급 -->
    <section v-if="mainView === 'roster'" class="panel roster-panel">
      <div v-if="showTeamLeaderReportOnly" class="team-leader-report-panel">
        <h2 class="team-leader-panel-title">평가완료보고서 서명</h2>
        <p class="team-leader-panel-desc">
          담당 팀원 {{ teamSignoff?.assigned_total ?? 0 }}명 평가가 모두 끝났습니다.
          아래 버튼으로 보고서에 서명해 주세요.
        </p>
      </div>
      <div v-else-if="showTeamLeaderResults" class="team-leader-results-head">
        <h2 class="team-leader-panel-title">팀 평가 결과</h2>
        <p class="team-leader-panel-desc">서명이 완료된 팀원 등급입니다. PDF는 아래에서 받을 수 있습니다.</p>
      </div>
      <div v-if="!showTeamLeaderReportOnly" class="roster-toolbar">
        <button
          v-if="!isTeamLeaderFlow || teamLeaderPhase === 'evaluate'"
          class="stitch-btn-primary btn-start-eval"
          type="button"
          :disabled="Boolean(period?.is_closed) || !rosterSource.length"
          @click="startEvaluation()"
        >
          평가 시작
        </button>
      </div>
      <p v-if="!showTeamLeaderReportOnly" class="roster-desc">{{ rosterDescription }}</p>

      <section v-if="siteGradeStatsPayload && !isTeamLeaderFlow" class="panel site-grade-stats-panel">
        <FeGradeStatsPanel
          :stats="siteGradeStatsPayload"
          :title="siteGradeStatsTitle"
          :subtitle="siteGradeStatsSubtitle"
        />
      </section>

      <!-- 소장 · 11명 초과 현장: 구역별 카드 -->
      <div v-if="showManagerBuckets && !activeManagerBucket" class="bucket-grid manager-bucket-grid">
        <button type="button" class="bucket-card bucket-card--direct" @click="selectManagerBucket('direct')">
          <span class="bucket-card__label">직영</span>
          <span class="bucket-card__count">{{ managerBucketCounts.direct }}</span>
          <span class="bucket-card__hint">소장 직접 평가 · 미완료 {{ managerBucketCounts.direct_incomplete }}명</span>
        </button>
        <button type="button" class="bucket-card bucket-card--leaders" @click="selectManagerBucket('team_leaders')">
          <span class="bucket-card__label">팀장평가</span>
          <span class="bucket-card__count">{{ managerBucketCounts.teams }}</span>
          <span class="bucket-card__hint">팀장 {{ managerBucketCounts.team_leaders }}명 · 팀원 {{ managerBucketCounts.team_workers }}명</span>
        </button>
        <button type="button" class="bucket-card bucket-card--pending" @click="selectManagerBucket('team_incomplete')">
          <span class="bucket-card__label">팀별 평가(미완료)</span>
          <span class="bucket-card__count">{{ managerBucketCounts.teams_incomplete }}</span>
          <span class="bucket-card__hint">평가가 끝나지 않은 팀</span>
        </button>
        <button type="button" class="bucket-card bucket-card--done" @click="selectManagerBucket('team_complete')">
          <span class="bucket-card__label">팀별 평가(완료)</span>
          <span class="bucket-card__count">{{ managerBucketCounts.teams_complete }}</span>
          <span class="bucket-card__hint">전원 평가 완료된 팀</span>
        </button>
        <button type="button" class="bucket-card bucket-card--sanctions" @click="selectManagerBucket('sanctions')">
          <span class="bucket-card__label">포상/제재 이력관리</span>
          <span class="bucket-card__count">{{ managerBucketCounts.sanctions_evidence }}</span>
          <span class="bucket-card__hint">포상·제재 이력 있는 근로자</span>
        </button>
      </div>

      <div v-if="showManagerBuckets && activeManagerBucket" class="bucket-list-head">
        <button type="button" class="stitch-btn-secondary back-btn" @click="managerBucketBack">
          ← {{ activeTeamLeaderId ? managerBucketTitle.replace(' 팀', '') + ' 팀 목록' : '전체 현황' }}
        </button>
        <h2 class="bucket-list-title">{{ managerBucketTitle }}</h2>
      </div>

      <ul
        v-if="showManagerBuckets && activeManagerBucket === 'team_leaders' && teamLeaderPersons.length && !activeTeamLeaderId"
        class="site-list team-leader-person-list"
      >
        <li v-for="w in teamLeaderPersons" :key="`tl-${w.id}`">
          <button type="button" class="site-list-item site-list-item--leader" @click="startEvaluation(w)">
            <div class="site-list-item__main">
              <strong>{{ w.name }}</strong>
              <span class="site-list-item__meta">팀장 · 소장 평가 대상</span>
            </div>
            <span :class="rosterStatusClass(w)" class="status-pill">{{ rosterStatusLabel(w) }}</span>
            <span class="chevron">›</span>
          </button>
        </li>
      </ul>

      <ul
        v-if="
          showManagerBuckets &&
          activeManagerBucket &&
          activeManagerBucket !== 'direct' &&
          activeManagerBucket !== 'team_leaders' &&
          !activeTeamLeaderId
        "
        class="site-list team-group-list"
      >
        <li v-for="team in visibleTeamGroups" :key="team.leaderLoginId">
          <button type="button" class="site-list-item" @click="selectTeamGroup(team.leaderLoginId)">
            <div class="site-list-item__main">
              <strong>{{ team.leaderLabel }}</strong>
              <span class="site-list-item__meta">팀원 {{ team.complete }}/{{ team.total }}명 완료</span>
            </div>
            <div class="site-list-item__progress">
              <span class="progress-pill">{{ team.complete }}/{{ team.total }}</span>
              <div class="progress-bar" aria-hidden="true">
                <div class="progress-bar__fill" :style="{ width: `${team.progressPct}%` }" />
              </div>
            </div>
            <span class="chevron">›</span>
          </button>
        </li>
        <li v-if="!visibleTeamGroups.length" class="muted empty-bucket">해당 구분의 팀이 없습니다.</li>
      </ul>

      <div v-if="!isManager && teamSignoff && (showTeamLeaderReportOnly || showTeamLeaderResults || !isTeamLeaderFlow)" class="approval-panel approval-panel--team-leader">
        <p class="approval-status">
          담당 팀원 {{ teamSignoff.assigned_total }}명 · {{ teamSignoff.evaluation_batch_label }}
          <span v-if="teamSignoff.signed"> · 서명 완료 ({{ teamSignoff.signed_at_label || teamSignoff.signed_at }})</span>
        </p>
        <p v-if="teamSignoff.can_sign && teamSignoff.s_over_limit" class="attendance-warn">
          기능/품질 S등급 20% 초과 — 서명 시 사유 입력 필요
        </p>
        <button
          v-if="teamSignoff.can_sign"
          class="stitch-btn-primary btn-approve-site"
          type="button"
          :disabled="submittingTeamSignoff || Boolean(period?.is_closed)"
          @click="openTeamSignoffModal"
        >
          {{ submittingTeamSignoff ? "제출 중…" : "평가완료보고서 서명" }}
        </button>
        <button
          v-if="teamSignoff.signed && teamSignoff.signature_id"
          class="stitch-btn-secondary"
          type="button"
          @click="downloadSignatureDoc(teamSignoff.signature_id)"
        >
          서명본 다운로드
        </button>
      </div>

      <div v-if="isManager && approval" class="approval-panel">
        <div class="approval-stats">
          <span>전체 {{ approval.site_complete_workers }}/{{ approval.site_total_workers }}명 완료</span>
          <span v-if="evaluator?.team_split_active"> · 직영 {{ approval.direct_complete }}/{{ approval.direct_total }}</span>
          <span v-if="approval.team_total"> · 팀원 {{ approval.team_complete }}/{{ approval.team_total }}</span>
        </div>
        <p class="approval-status">{{ approval.status_label }}</p>
        <p v-if="approval.can_submit_site_approval && approval.s_over_limit" class="attendance-warn">
          기능/품질 S등급 20% 초과 — 최종 제출 서명 시 사유 입력 필요
        </p>
        <p v-if="!approval.team_leaders_all_signed" class="attendance-warn">
          모든 팀장의 평가완료보고서 서명 후 소장 최종 제출을 진행할 수 있습니다.
        </p>
        <ul v-if="teamLeaderReports.length" class="team-report-list">
          <li v-for="report in teamLeaderReports" :key="report.team_leader_login_id">
            <div class="team-report-item">
              <strong>{{ report.team_leader_name }}</strong>
              <span class="meta">
                팀원 {{ report.team_worker_count }}명
                · 팀장 {{ report.team_leader_signed ? "서명완료" : "미서명" }}
              </span>
              <p class="team-report-hint muted">
                팀장이 등록한 평가·포상·제재 내용을 확인하세요. 점수에 이견이 있으면 반려하세요.
              </p>
              <div class="team-report-actions">
                <button
                  v-if="report.team_leader_signature_id"
                  type="button"
                  class="link-btn"
                  @click="downloadSignatureDoc(report.team_leader_signature_id)"
                >
                  팀장 보고서
                </button>
                <button
                  v-if="report.can_manager_reject"
                  type="button"
                  class="stitch-btn-secondary danger-outline"
                  :disabled="Boolean(period?.is_closed) || rejectingTeamReport"
                  @click="rejectTeamReport(report.team_leader_login_id, report.team_leader_name)"
                >
                  평가 반려
                </button>
              </div>
            </div>
          </li>
        </ul>
        <p v-if="!approval.team_leaders_all_signed && approval.can_submit_site_approval === false" class="attendance-warn">
          (위 조건 충족 후 현장 전체 승인 가능)
        </p>
        <button
          v-if="approval.can_submit_site_approval"
          class="stitch-btn-primary btn-approve-site"
          type="button"
          :disabled="submittingApproval || Boolean(period?.is_closed)"
          @click="openSiteApprovalModal"
        >
          {{ submittingApproval ? "제출 중…" : "평가완료보고서 최종 제출 (서명)" }}
        </button>
      </div>

      <div v-if="mySignatures.length" class="signatures-panel">
        <h3 class="signatures-title">내 서명본</h3>
        <ul class="signatures-list">
          <li v-for="sig in mySignatures" :key="String(sig.id)">
            <span>{{ sig.stage_label || sig.evaluation_batch_label || "서명" }} · {{ sig.signed_at_label || sig.signed_at || "—" }}</span>
            <button
              v-if="sig.has_document && typeof sig.id === 'number'"
              type="button"
              class="link-btn"
              @click="downloadSignatureDoc(sig.id)"
            >
              PDF
            </button>
            <button
              v-else-if="sig.consent"
              type="button"
              class="link-btn"
              @click="downloadConsentDoc"
            >
              PDF
            </button>
          </li>
        </ul>
      </div>

      <div
        v-if="
          !showTeamLeaderReportOnly &&
          (
            !showManagerBuckets ||
            activeManagerBucket === 'direct' ||
            activeManagerBucket === 'sanctions' ||
            activeTeamLeaderId
          )
        "
        class="table-wrap roster-table-wrap"
      >
        <table class="data-table roster-table">
          <thead>
            <tr>
              <th>번호</th>
              <th>성명</th>
              <th v-if="isManager && evaluator?.team_split_active">구분</th>
              <th>기능 (2-1)</th>
              <th class="col-safety-sanction">안전·제재 (2-2)</th>
              <th class="col-status">상태</th>
              <th class="col-remark">비고</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(w, idx) in rosterDisplayWorkers" :key="w.id" :class="workerRowHighlightClass(w)">
              <td>{{ idx + 1 }}</td>
              <td>{{ w.name }}</td>
              <td v-if="isManager && evaluator?.team_split_active">{{ assignmentLabel(w) }}</td>
              <td>
                <span :class="gradeDisplayClass(w.functional_assessment)">{{ gradeDisplayLabel(w.functional_assessment) }}</span>
              </td>
              <td class="safety-sanction-cell">
                <span :class="safetySanctionLineClass(w)">{{ safetySanctionLineText(w) }}</span>
              </td>
              <td class="status-cell">
                <button
                  class="status-pill status-pill-link status-pill--compact"
                  :class="rosterStatusClass(w)"
                  type="button"
                  :disabled="!canEvaluateWorker(w) || workerEvalStatusKey(w) === 'complete'"
                  @click="onRosterStatusClick(w)"
                >
                  {{ rosterStatusLabel(w) }}
                </button>
                <span v-if="evaluationLocked" class="muted-action status-locked-hint">승인 중</span>
              </td>
              <td class="remark-cell">{{ w.remark || "—" }}</td>
              <td class="actions-cell">
                <div v-if="workerEvidenceChips(w).length" class="evidence-chips">
                  <button
                    v-for="chip in workerEvidenceChips(w)"
                    :key="chip.key"
                    type="button"
                    class="evidence-chip"
                    :class="chip.tone === 'reward' ? 'evidence-chip--reward' : 'evidence-chip--sanction'"
                    :title="chip.title"
                    @click="chip.onClick()"
                  >
                    <span class="evidence-chip__tag">{{ chip.tag }}</span>
                    <span class="evidence-chip__kind">{{ chip.kind }}</span>
                    <img
                      v-if="chip.thumbUrl"
                      class="evidence-chip__thumb"
                      :src="chip.thumbUrl"
                      alt=""
                    />
                  </button>
                </div>
                <button
                  v-if="canOpenHistory(w)"
                  class="link-btn"
                  type="button"
                  @click="openHistory(w)"
                >
                  제재이력
                </button>
                <button
                  v-if="canRegisterSanction(w)"
                  class="link-btn"
                  type="button"
                  @click="openSanction(w)"
                >
                  제재
                </button>
                <button
                  v-if="canUploadReward(w)"
                  class="link-btn"
                  type="button"
                  @click="openRewardUpload(w)"
                >
                  포상
                </button>
              </td>
            </tr>
            <tr v-if="!rosterDisplayWorkers.length">
              <td :colspan="rosterColspan" class="empty-cell">검색 결과가 없습니다.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <FunctionalEvalWorkspace
      v-if="mainView === 'evaluate' && evalCriteria.length"
      :key="evalSessionKey"
      :workers="evaluableWorkers"
      :eval-type="currentEvalType"
      :title="evalTabTitle"
      :criteria="evalCriteria"
      :period-closed="Boolean(period?.is_closed) || evaluationLocked"
      :evidence-submit-blocked="evidenceSubmitBlocked"
      :evaluation-locked="evaluationLocked"
      :focus-worker-id="focusWorkerId"
      :auto-pick-on-mount="isFeGuidePreview()"
      :grouped-violations="groupedViolations"
      :sanction-prompt-message="sanctionPromptMessage"
      :default-violation-code="form.violation_code"
      :reload="load"
      @request-safety="onRequestSafety"
      @safety-saved="onSafetySaved"
      @revision-saved="onRevisionSaved"
      @sanction-saved="onSanctionRegistered"
      @reward-saved="onRewardRegistered"
      @open-history="openHistoryById"
    />

    <!-- 제재·이력 모달 (모바일 바텀시트 / 데스크톱 중앙 모달) -->
    <Teleport to="body">
      <div
        v-if="selectedWorker || historyWorker || rewardWorker"
        class="fe-overlay-backdrop"
        aria-hidden="true"
        @click="closePanels"
      />
      <section
        v-if="selectedWorker"
        class="panel sanction-form fe-dialog"
        :class="dialogShellClass"
        role="dialog"
        aria-modal="true"
        :aria-label="`${selectedWorker.name} 제재 등록`"
        @click.stop
      >
        <div v-if="isMobileViewport" class="fe-sheet-handle" aria-hidden="true" />
        <div class="dialog-head">
          <h2>{{ selectedWorker.name }} — 위반·제재</h2>
          <button class="link-btn dialog-close" type="button" aria-label="닫기" @click="closeForm">✕</button>
        </div>
        <p v-if="sanctionPromptMessage" class="sanction-hint">{{ sanctionPromptMessage }}</p>
        <p v-else-if="period?.is_closed" class="sanction-hint">
          마감 후 제재 이력 제출 — 본사 승인 후 감점·등급에 반영됩니다. 등록 후 수정·삭제할 수 없습니다.
        </p>
        <FeSanctionRegisterForm
          v-if="selectedWorker"
          :key="`${selectedWorker.id}-${sanctionFormKey}`"
          :worker-id="selectedWorker.id"
          :worker-name="selectedWorker.name"
          :grouped-violations="groupedViolations"
          :default-violation-code="form.violation_code"
          :default-note="form.note"
          :focus-comment="Boolean(form.note)"
          :disabled="evidenceSubmitBlocked"
          @saved="onSanctionFormSaved"
          @cancel="closeForm"
        />
      </section>

      <section
        v-if="rewardWorker"
        class="panel sanction-form fe-dialog"
        :class="dialogShellClass"
        role="dialog"
        aria-modal="true"
        :aria-label="`${rewardWorker.name} 고객사 포상`"
        @click.stop
      >
        <div v-if="isMobileViewport" class="fe-sheet-handle" aria-hidden="true" />
        <div class="dialog-head">
          <h2>{{ rewardWorker.name }} — 고객사 포상 사진</h2>
          <button class="link-btn dialog-close" type="button" aria-label="닫기" @click="closeRewardUpload">✕</button>
        </div>
        <p class="sanction-hint">
          <template v-if="period?.is_closed">
            마감 후 포상 이력 제출 — 본사 승인 후 가점이 반영됩니다. 제출 후 회수·변경할 수 없습니다.
          </template>
          <template v-else>
            포상 사진을 올리면 본사 승인 후 비고에 「고객사포상(+5)」이 표시됩니다. 제출 후에는 회수·변경할 수 없습니다.
          </template>
        </p>
        <ul v-if="rewardHistory.length" class="reward-history">
          <li v-for="r in rewardHistory" :key="r.id">
            <span class="reward-status">{{ rewardStatusLabel(r.status) }}</span>
            <span v-if="r.status === 'APPROVED'" class="muted">+{{ r.bonus_points ?? 5 }}점</span>
            <button class="link-btn" type="button" @click="previewRewardPhoto(r.id)">사진 보기</button>
          </li>
        </ul>
        <label v-if="!rewardReadOnly" class="field">
          <span class="field-label">포상 사진</span>
          <input ref="rewardPhotoInput" type="file" accept="image/jpeg,image/png,image/webp" class="field-control" @change="onRewardPhotoChange" />
        </label>
        <div v-if="rewardPreviewUrl && !rewardReadOnly" class="reward-preview">
          <img :src="rewardPreviewUrl" alt="선택한 포상 사진 미리보기" />
        </div>
        <div v-if="!rewardReadOnly" class="actions" :class="{ 'actions-sticky': isMobileViewport }">
          <button class="stitch-btn-secondary touch-btn" type="button" @click="closeRewardUpload">취소</button>
          <button
            class="stitch-btn-primary touch-btn"
            type="button"
            :disabled="!rewardPhotoFile || rewardUploading || rewardHasSubmitted || evidenceSubmitBlocked"
            @click="submitRewardUpload"
          >
            {{ rewardUploading ? "제출 중…" : rewardHasSubmitted ? "제출 완료" : "본사 승인 요청" }}
          </button>
        </div>
        <div v-else class="actions" :class="{ 'actions-sticky': isMobileViewport }">
          <button class="stitch-btn-secondary touch-btn" type="button" @click="closeRewardUpload">닫기</button>
        </div>
        <p v-if="rewardError" class="error">{{ rewardError }}</p>
      </section>

      <section
        v-if="historyWorker"
        class="panel history-panel fe-dialog"
        :class="dialogShellClass"
        role="dialog"
        aria-modal="true"
        :aria-label="`${historyWorker.name} 이력`"
        @click.stop
      >
        <div v-if="isMobileViewport" class="fe-sheet-handle" aria-hidden="true" />
        <div class="dialog-head history-head">
          <h2>{{ historyWorker.name }} — 평가·제재 이력</h2>
          <button class="dialog-close" type="button" aria-label="닫기" @click="closeHistory">✕</button>
        </div>
        <p v-if="!historyData?.history_visible" class="warn">{{ historyData?.message }}</p>
        <div v-else class="history-sections">
          <section v-if="allHistoryAssessments.length" class="history-block">
            <h3>과거 평가 등급</h3>
            <ul class="history-list">
              <li v-for="(a, i) in allHistoryAssessments" :key="`a-${i}`">
                <span v-if="a.from_prior_period" class="tag">이전</span>
                {{ a.period_title || `기간 ${a.period_id}` }}
                — 기능 {{ gradeDisplayLabel(a.functional_assessment) }} · 안전 {{ gradeDisplayLabel(a.safety_assessment) }}
              </li>
            </ul>
          </section>
          <section class="history-block">
            <h3>제재 이력</h3>
            <ul class="history-list">
              <li v-for="s in allHistorySanctions" :key="`${s.id}-h`">
                <span v-if="s.from_prior_period" class="tag">이전</span>
                {{ s.violation_label }} →
                <span :class="sanctionOutcomeClass(s)">{{ sanctionHistoryLabel(s) }}</span>
                <span v-if="s.penalty_points" class="meta"> · -{{ s.penalty_points }}점</span>
                <span class="meta">{{ formatDateTimeKst(s.created_at, "—") }}</span>
                <span v-if="s.reported_by_name" class="meta"> · {{ s.reported_by_name }}</span>
                <span v-if="s.evidence_type_label" class="meta"> · {{ s.evidence_type_label }}</span>
                <button
                  v-if="s.evidence_photo_url"
                  class="link-btn"
                  type="button"
                  @click="previewSanctionEvidence(s.id, historyWorker?.name || '근로자', `${s.violation_label} · ${s.evidence_type_label || '사진'}`)"
                >
                  근거 사진
                </button>
                <button
                  v-else-if="s.note"
                  class="link-btn"
                  type="button"
                  @click="openSanctionTextFromHistory(historyWorker?.name || '근로자', s)"
                >
                  근거 텍스트
                </button>
              </li>
              <li v-if="!allHistorySanctions.length">제재 이력 없음</li>
            </ul>
          </section>
          <section v-if="historyData?.assessment_revisions?.length" class="history-block">
            <h3>점수 수정 이력</h3>
            <ul class="history-list">
              <li v-for="r in historyData.assessment_revisions" :key="`r-${r.id}`">
                {{ r.eval_type === "SAFETY" ? "2-2 안전" : "2-1 기능" }}
                {{ r.before_grade_code || "—" }} → {{ r.after_grade_code }}
                <span class="meta">{{ formatDateTimeKst(r.created_at, "—") }}</span>
                <span v-if="r.edited_by_name" class="meta"> · {{ r.edited_by_name }}</span>
                <span class="meta history-note"> — {{ r.reason }}</span>
              </li>
            </ul>
          </section>
        </div>
        <div v-if="historyData?.adjustments || historyData?.mileage" class="points-box">
          <h3>가감점</h3>
          <p v-if="historyAdjustments.penalty_points" class="points-line points-line--penalty">
            {{ historyAdjustments.penalty_label }}
          </p>
          <p v-if="historyAdjustments.bonus_points" class="points-line points-line--bonus">
            {{ historyAdjustments.bonus_label }}
          </p>
          <p v-if="!historyAdjustments.penalty_points && !historyAdjustments.bonus_points" class="muted">
            등록된 감점·가점 없음
          </p>
        </div>
      </section>
    </Teleport>

    <div
      v-if="evidenceModal"
      class="evidence-modal-backdrop"
      role="dialog"
      aria-modal="true"
      :aria-label="evidenceModal.title"
      @click="closeEvidenceModal"
    >
      <section class="evidence-modal panel" @click.stop>
        <div class="dialog-head">
          <h2>{{ evidenceModal.title }}</h2>
          <button type="button" class="link-btn dialog-close" aria-label="닫기" @click="closeEvidenceModal">✕</button>
        </div>
        <p v-if="evidenceModal.subtitle" class="evidence-modal-subtitle">{{ evidenceModal.subtitle }}</p>
        <img
          v-if="evidenceModal.mode === 'photo' && evidenceModal.photoUrl"
          class="evidence-modal-photo"
          :src="evidenceModal.photoUrl"
          alt=""
        />
        <p v-else-if="evidenceModal.mode === 'text'" class="evidence-modal-text">{{ evidenceModal.text }}</p>
        <template v-else-if="evidenceModal.mode === 'sanction'">
          <p v-if="evidenceModal.text" class="evidence-modal-text">{{ evidenceModal.text }}</p>
          <img
            v-if="evidenceModal.photoUrl"
            class="evidence-modal-photo"
            :src="evidenceModal.photoUrl"
            alt="제재 근거 사진"
          />
          <div v-if="evidenceModal.signatureUrl" class="evidence-modal-signature">
            <p class="evidence-modal-signature-label">등록자 전자서명 (수정·삭제 불가)</p>
            <img class="evidence-modal-signature-img" :src="evidenceModal.signatureUrl" alt="제재 등록 서명" />
          </div>
        </template>
        <p v-if="evidenceModal.readOnlyNote" class="evidence-modal-readonly">{{ evidenceModal.readOnlyNote }}</p>
      </section>
    </div>

    <FeSignatureModal
      ref="signatureModalRef"
      :open="signatureModalOpen"
      :title="signatureModalTitle"
      :description="signatureModalDescription"
      :submit-label="signatureModalSubmitLabel"
      :grade-review="signatureGradeReview"
      @update:open="(v) => (signatureModalOpen = v)"
      @submit="onSignatureModalSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import FunctionalEvalWorkspace from "@/components/functional-eval/FunctionalEvalWorkspace.vue";
import FeSanctionRegisterForm from "@/components/functional-eval/FeSanctionRegisterForm.vue";
import FeSignatureModal from "@/components/functional-eval/FeSignatureModal.vue";
import type { GradeInflationReview } from "@/components/functional-eval/FeGradeInflationReview.vue";
import FeGradeStatsPanel, { type GradeStatsPayload } from "@/components/functional-eval/FeGradeStatsPanel.vue";
import type { Criterion } from "@/components/functional-eval/EvalAssessmentSheet.vue";
import { useMobileViewport } from "@/composables/useMobileViewport";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/services/api";
import {
  countIncompleteWorkers,
  findNextIncompleteWorker,
  gradeDisplayClass,
  gradeDisplayLabel,
  isEvalIncomplete,
  isFunctionalComplete,
  isSafetyComplete,
  isFullyComplete,
  needsSanctionPrompt,
  safetySanctionDisplay,
  safetySanctionLine,
  workerRowHighlightClass,
} from "@/utils/functionalEvalCompletion";
import { buildSanctionPrefillFromSafetyScores } from "@/utils/safetySanctionMapping";
import { getFeGuideScene, isFeGuidePreview } from "@/utils/feGuidePreview";
import { downloadBlobAsFile } from "@/utils/blobDownload";
import { useFeSiteSessionStore, type TeamLeaderPhase } from "@/stores/feSiteSession";
import { useAuthStore } from "@/stores/auth";
import { formatDateTimeKst } from "@/utils/datetime";

type MainView = "roster" | "evaluate";
type EvalTab = "functional" | "safety";
type EvalType = "FUNCTIONAL" | "SAFETY";
type EvalStatusKey = "incomplete" | "in_progress" | "complete";
type EvalStatusFilter = EvalStatusKey | "all";
type ManagerBucket = "direct" | "team_leaders" | "team_incomplete" | "team_complete" | "sanctions";

interface TeamGroup {
  leaderLoginId: string;
  leaderLabel: string;
  workers: Worker[];
  total: number;
  complete: number;
  progressPct: number;
}

interface AssessmentBrief {
  scores: Record<string, string>;
  total_score: number;
  max_score: number;
  grade_code: string;
  grade_label: string;
  is_complete: boolean;
}

interface EvalCatalogBlock {
  title: string;
  criteria: Criterion[];
  max_score: number;
}

interface EvaluatorSession {
  role: "MANAGER" | "TEAM_LEADER";
  role_label: string;
  manager_login_id?: string;
  eval_scope_label?: string;
  login_id: string;
  display_name: string;
  site_code: string;
  site_alias: string;
  manager_name: string;
  assigned_worker_count: number;
  site_worker_count: number;
  team_split_active: boolean;
  split_threshold: number;
}

interface ApprovalPayload {
  status: string;
  status_label: string;
  site_total_workers: number;
  site_complete_workers: number;
  direct_total: number;
  direct_complete: number;
  team_total: number;
  team_complete: number;
  incomplete_count: number;
  can_submit_site_approval: boolean;
  evaluation_editable: boolean;
  team_leaders_all_signed?: boolean;
  team_reports_all_manager_approved?: boolean;
  team_leader_reports?: TeamLeaderReportPayload[];
  reject_note?: string | null;
  s_over_limit?: boolean;
  no_c_grade?: boolean;
  grade_distribution_snapshot?: GradeInflationReview["grade_distribution_snapshot"];
}

interface TeamLeaderReportPayload {
  team_leader_login_id: string;
  team_leader_name: string;
  team_worker_count: number;
  team_leader_signed: boolean;
  team_leader_signed_at?: string | null;
  can_manager_reject?: boolean;
  manager_approved?: boolean;
  manager_approved_at?: string | null;
  can_manager_approve?: boolean;
  team_leader_signature_id?: number | null;
  manager_approval_signature_id?: number | null;
}

interface TeamSignoffPayload {
  evaluation_batch: number;
  evaluation_batch_label: string;
  assigned_total: number;
  incomplete_count: number;
  can_sign: boolean;
  signed: boolean;
  signed_at?: string | null;
  signed_at_label?: string | null;
  signature_id?: number | null;
  s_over_limit?: boolean;
  no_c_grade?: boolean;
  grade_distribution_snapshot?: GradeInflationReview["grade_distribution_snapshot"];
}

interface SignatureListItem {
  id: number | string;
  stage_label?: string;
  evaluation_batch_label?: string;
  signed_at?: string | null;
  signed_at_label?: string | null;
  has_document?: boolean;
  consent?: boolean;
}

interface Period {
  id: number;
  deadline_date: string;
  is_closed: boolean;
  last_attendance_date?: string | null;
  attendance_row_count?: number;
}

interface ViolationItem {
  code: string;
  category: string;
  category_label: string;
  label: string;
}

interface Worker {
  id: number;
  row_no: number;
  name: string;
  eval_assignment?: "DIRECT" | "TEAM" | "TEAM_LEADER";
  eval_assignment_label?: string;
  assigned_evaluator_login_id?: string | null;
  sanction_status: string;
  sanction_status_label: string;
  sanction_count?: number;
  latest_sanction?: {
    id: number;
    violation_label?: string | null;
    sanction_result_label?: string | null;
    note?: string | null;
    evidence_type?: string | null;
    evidence_photo_url?: string | null;
    has_signature?: boolean;
    signature_url?: string | null;
  } | null;
  is_permanently_expelled: boolean;
  history_visible: boolean;
  functional_assessment?: AssessmentBrief | null;
  safety_assessment?: AssessmentBrief | null;
  remark?: string;
  mileage?: { status?: string; label?: string; points?: number };
  customer_reward?: { id: number; status: string; bonus_points?: number } | null;
}

interface AssessmentHistoryRow {
  period_id: number;
  period_title?: string;
  functional_assessment?: AssessmentBrief | null;
  safety_assessment?: AssessmentBrief | null;
  from_prior_period?: boolean;
}

interface SanctionRow {
  id: number;
  violation_label: string;
  sanction_result_label: string;
  institutional_sanction_label?: string;
  outcome_label?: string;
  sanction_display_label?: string;
  is_hiring_ban?: boolean;
  strike_number: number;
  note?: string | null;
  reported_by_name?: string | null;
  penalty_points?: number;
  evidence_type_label?: string;
  evidence_photo_url?: string | null;
  created_at: string;
  from_prior_period?: boolean;
}

interface RevisionRow {
  id: number;
  eval_type: string;
  before_grade_code?: string | null;
  after_grade_code: string;
  reason: string;
  edited_by_name?: string | null;
  created_at: string;
}

interface EvidenceChipView {
  key: string;
  tag: string;
  kind: string;
  tone: "reward" | "sanction";
  title: string;
  thumbUrl?: string;
  onClick: () => void;
}

interface EvidenceModalState {
  title: string;
  subtitle?: string;
  mode: "photo" | "text" | "sanction";
  photoUrl?: string;
  text?: string;
  signatureUrl?: string;
  readOnlyNote?: string;
}

const { isMobileViewport } = useMobileViewport();
const route = useRoute();
const router = useRouter();
const feSiteSession = useFeSiteSessionStore();
const auth = useAuthStore();

const evalStatusFromLabel: Record<string, EvalStatusKey> = {
  미완료: "incomplete",
  진행중: "in_progress",
  완료: "complete",
  미평가: "incomplete",
  평가완료: "complete",
  incomplete: "incomplete",
  in_progress: "in_progress",
  complete: "complete",
};

const mainView = computed<MainView>(() =>
  route.name === "site-functional-eval-evaluate" ? "evaluate" : "roster",
);

const activeEvalStatus = computed<EvalStatusFilter>(() => {
  const q = typeof route.query.eval_status === "string" ? route.query.eval_status : "";
  return evalStatusFromLabel[q] ?? "all";
});

const activeTab = ref<EvalTab>("functional");
const focusWorkerId = ref<number | null>(null);
const evalSessionKey = ref(0);
const sanctionPromptMessage = ref("");
const sanctionFormKey = ref(0);
const saveNotice = ref("");
let saveNoticeTimer: ReturnType<typeof setTimeout> | null = null;
const activeManagerBucket = ref<ManagerBucket | null>(null);
const activeTeamLeaderId = ref<string | null>(null);
const evalCatalog = ref<{ FUNCTIONAL: EvalCatalogBlock; SAFETY: EvalCatalogBlock } | null>(null);
const period = ref<Period | null>(null);
const evaluator = ref<EvaluatorSession | null>(null);
const attendanceMessage = ref("");
const workers = ref<Worker[]>([]);
const siteGradeStats = ref<Record<string, unknown> | null>(null);
const siteGradeStatsPayload = computed((): GradeStatsPayload | null => {
  if (!siteGradeStats.value) return null;
  return {
    functional: siteGradeStats.value.functional as GradeStatsPayload["functional"],
    safety: siteGradeStats.value.safety as GradeStatsPayload["safety"],
  };
});
const siteGradeStatsTitle = computed(() => {
  const name = String(siteGradeStats.value?.site_name || "현장");
  const team = siteGradeStats.value?.team_label;
  return team ? `${name}` : name;
});
const siteGradeStatsSubtitle = computed(() => {
  const team = String(siteGradeStats.value?.team_label || "");
  const contractor = String(siteGradeStats.value?.contractor_label || "").trim();
  const workersTotal = (siteGradeStats.value?.functional as { workers_total?: number } | undefined)?.workers_total;
  const parts = [team, contractor, workersTotal != null && `근로자 ${workersTotal}명`].filter(Boolean);
  return parts.join(" · ");
});
const siteOverview = ref<Worker[]>([]);
const approval = ref<ApprovalPayload | null>(null);
const teamSignoff = ref<TeamSignoffPayload | null>(null);
const mySignatures = ref<SignatureListItem[]>([]);
const submittingApproval = ref(false);
const submittingTeamSignoff = ref(false);
const rejectingTeamReport = ref(false);
const signatureModalOpen = ref(false);
const signatureModalRef = ref<InstanceType<typeof FeSignatureModal> | null>(null);
const signatureModalMode = ref<"team" | "site">("site");
const signatureModalTitle = computed(() => {
  if (signatureModalMode.value === "team") return "팀원 평가완료보고서 서명";
  return "현장 평가완료보고서 제출";
});
const signatureModalDescription = computed(() => {
  if (signatureModalMode.value === "team") {
    return "담당 팀원 등급표가 포함된 평가완료보고서입니다. 서명 후 소장 검토를 받습니다. 포상·제재 근거는 제출 후 변경할 수 없습니다.";
  }
  return "팀장 보고서·직영 평가표를 포함한 갑지에 서명하면 본사로 제출됩니다.";
});
const signatureModalSubmitLabel = computed(() => {
  if (signatureModalMode.value === "team") return "평가완료보고서 서명";
  return "최종 제출 및 서명";
});

const signatureGradeReview = computed((): GradeInflationReview | null => {
  if (signatureModalMode.value === "team" && teamSignoff.value) {
    return {
      s_over_limit: teamSignoff.value.s_over_limit,
      no_c_grade: teamSignoff.value.no_c_grade,
      grade_distribution_snapshot: teamSignoff.value.grade_distribution_snapshot,
    };
  }
  if (signatureModalMode.value === "site" && approval.value) {
    return {
      s_over_limit: approval.value.s_over_limit,
      no_c_grade: approval.value.no_c_grade,
      grade_distribution_snapshot: approval.value.grade_distribution_snapshot,
    };
  }
  return null;
});

const teamLeaderReports = computed(() => approval.value?.team_leader_reports || []);
const violations = ref<ViolationItem[]>([]);
const selectedWorker = ref<Worker | null>(null);
const rewardWorker = ref<Worker | null>(null);
const rewardPhotoFile = ref<File | null>(null);
const rewardPhotoInput = ref<HTMLInputElement | null>(null);
const rewardUploading = ref(false);
const rewardError = ref("");
const rewardHistory = ref<Array<{ id: number; status: string; bonus_points?: number }>>([]);
const rewardPreviewUrl = ref<string | null>(null);
const rewardReadOnly = ref(false);
const rewardThumbUrls = ref<Record<number, string>>({});
const rewardFullUrls = ref<Record<number, string>>({});
const sanctionThumbUrls = ref<Record<number, string>>({});
const sanctionFullUrls = ref<Record<number, string>>({});
const sanctionSignatureUrls = ref<Record<number, string>>({});
const evidenceModal = ref<EvidenceModalState | null>(null);
const EVIDENCE_THUMB_MAX_EDGE = 72;
const rewardHasSubmitted = computed(() => rewardHistory.value.length > 0);
const historyWorker = ref<Worker | null>(null);
const historyData = ref<{
  history_visible: boolean;
  message?: string;
  sanctions: SanctionRow[];
  prior_sanctions: SanctionRow[];
  prior_assessments?: AssessmentHistoryRow[];
  assessment_revisions?: RevisionRow[];
  adjustments?: { penalty_points?: number; bonus_points?: number; penalty_label?: string; bonus_label?: string };
  mileage?: { penalty_points?: number; bonus_points?: number; penalty_label?: string; bonus_label?: string; points?: number };
} | null>(null);
const saving = ref(false);
const exportingGrade = ref(false);
const error = ref("");
const form = reactive({ violation_code: "", note: "" });

const currentEvalType = computed<EvalType>(() => (activeTab.value === "safety" ? "SAFETY" : "FUNCTIONAL"));

const evalTabTitle = computed(() => {
  const block = evalCatalog.value?.[currentEvalType.value];
  return block?.title || (activeTab.value === "safety" ? "2-2 안전·제재" : "2-1 기능인정제 평가");
});

const evalCriteria = computed(() => evalCatalog.value?.[currentEvalType.value]?.criteria || []);

const incompleteCount = computed(() => {
  if (isTeamLeaderFlow.value) {
    return teamSignoff.value?.incomplete_count ?? countIncompleteWorkers(workers.value);
  }
  if (isManager.value && evaluator.value?.team_split_active) {
    return evaluableIncompleteCount.value;
  }
  return approval.value?.incomplete_count ?? countIncompleteWorkers(rosterSource.value);
});

const managerEvalQueue = computed(() =>
  isManager.value && evaluator.value?.team_split_active ? workers.value : rosterSource.value,
);

const evaluableIncompleteCount = computed(() =>
  managerEvalQueue.value.filter((w) => isEvalIncomplete(w) && isManagerEvaluable(w)).length,
);

const canStartFromIncomplete = computed(() =>
  !Boolean(period?.value?.is_closed)
  && evaluableIncompleteCount.value > 0,
);


const isManager = computed(() => {
  if (!evaluator.value) return false;
  return evaluator.value.role === "MANAGER";
});

const teamLeaderPhase = computed((): TeamLeaderPhase => {
  if (isManager.value || !evaluator.value) return null;
  if (teamSignoff.value?.signed) return "results";
  if (evaluableIncompleteCount.value === 0 && teamSignoff.value) return "report";
  return "evaluate";
});

const isTeamLeaderFlow = computed(() => !isManager.value && Boolean(evaluator.value));
const showTeamLeaderReportOnly = computed(
  () => isTeamLeaderFlow.value && teamLeaderPhase.value === "report" && mainView.value === "roster",
);
const showTeamLeaderResults = computed(
  () => isTeamLeaderFlow.value && teamLeaderPhase.value === "results" && mainView.value === "roster",
);

const rosterSource = computed(() =>
  isManager.value && siteOverview.value.length ? siteOverview.value : workers.value,
);
const evaluationLocked = computed(() => approval.value?.evaluation_editable === false);
const evidenceSubmitBlocked = computed(() => !period.value?.is_closed && evaluationLocked.value);

const evaluatorHeadline = computed(() => {
  if (!evaluator.value) return "";
  if (evaluator.value.eval_scope_label) return `${evaluator.value.role_label} · ${evaluator.value.eval_scope_label}`;
  if (!isManager.value) {
    return `팀장 · 담당 ${evaluator.value.assigned_worker_count}명`;
  }
  return "소장 평가";
});

const evaluatorBadgeClass = computed(() =>
  isManager.value ? "evaluator-badge--manager" : "evaluator-badge--leader",
);

const evaluatorHint = computed(() => {
  if (approval.value?.status_label && approval.value.status !== "IN_PROGRESS") {
    return approval.value.status_label + (approval.value.reject_note ? ` — ${approval.value.reject_note}` : "");
  }
  if (!evaluator.value) return "";
  if (!isManager.value) {
    return "담당 팀원 평가 완료 후 「평가완료보고서」에 서명하세요. 포상·제재 근거는 제출 후 변경할 수 없습니다.";
  }
  if (evaluator.value.team_split_active) {
    return "팀원 평가는 팀장 담당입니다. 포상·제재는 소장·팀장 모두 등록할 수 있으며, 팀장은 담당 팀원에만 등록합니다. 팀장 보고서 검토 후 최종 서명하여 본사로 제출합니다.";
  }
  return "10명 이하 현장은 소장이 전원 평가합니다. 완료 후 소장 승인 → 안전보건실 → 대표이사 순으로 확정됩니다.";
});

const rosterDescription = computed(() => evaluatorHint.value);

const rosterColspan = computed(() => (isManager.value && evaluator.value?.team_split_active ? 8 : 7));

const showManagerBuckets = computed(
  () => isManager.value && Boolean(evaluator.value?.team_split_active) && mainView.value === "roster",
);

const teamGroups = computed((): TeamGroup[] => {
  const map = new Map<string, Worker[]>();
  for (const w of siteOverview.value) {
    if (w.eval_assignment !== "TEAM") continue;
    const key = (w.assigned_evaluator_login_id || "").trim() || "미배정";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(w);
  }
  return [...map.entries()]
    .map(([leaderLoginId, members]) => {
      const complete = members.filter((m) => isFullyComplete(m)).length;
      const total = members.length;
      return {
        leaderLoginId,
        leaderLabel: teamLeaderLabel(leaderLoginId),
        workers: members,
        total,
        complete,
        progressPct: total > 0 ? Math.round((complete / total) * 100) : 0,
      };
    })
    .sort((a, b) => a.leaderLabel.localeCompare(b.leaderLabel, "ko"));
});

function isTeamFullyComplete(team: TeamGroup): boolean {
  return team.total > 0 && team.complete >= team.total;
}

const teamLeaderPersons = computed(() =>
  siteOverview.value.filter((w) => w.eval_assignment === "TEAM_LEADER"),
);

function hasActualSanctionHistory(w: Worker): boolean {
  return Boolean((w.sanction_count ?? 0) > 0 || w.latest_sanction);
}

function hasRewardOrSanctionEvidence(w: Worker): boolean {
  return Boolean(w.customer_reward?.id || hasActualSanctionHistory(w));
}

const sanctionsEvidenceWorkers = computed(() =>
  siteOverview.value.filter((w) => hasRewardOrSanctionEvidence(w)),
);

const managerBucketCounts = computed(() => {
  const directWorkers = siteOverview.value.filter((w) => isDirectWorker(w));
  const directIncomplete = directWorkers.filter((w) => isEvalIncomplete(w)).length;
  const teams = teamGroups.value;
  return {
    direct: directWorkers.length,
    direct_incomplete: directIncomplete,
    team_leaders: teamLeaderPersons.value.length,
    teams: teams.length,
    team_workers: teams.reduce((sum, t) => sum + t.total, 0),
    teams_incomplete: teams.filter((t) => !isTeamFullyComplete(t)).length,
    teams_complete: teams.filter((t) => isTeamFullyComplete(t)).length,
    sanctions_evidence: sanctionsEvidenceWorkers.value.length,
  };
});

const managerBucketTitle = computed(() => {
  if (activeTeamLeaderId.value) {
    const team = teamGroups.value.find((t) => t.leaderLoginId === activeTeamLeaderId.value);
    return team ? `${team.leaderLabel} 팀` : "팀 상세";
  }
  if (activeManagerBucket.value === "direct") return "직영 평가";
  if (activeManagerBucket.value === "team_leaders") return "팀장평가";
  if (activeManagerBucket.value === "team_incomplete") return "팀별 평가(미완료)";
  if (activeManagerBucket.value === "team_complete") return "팀별 평가(완료)";
  if (activeManagerBucket.value === "sanctions") return "포상/제재 이력관리";
  return "";
});

const visibleTeamGroups = computed(() => {
  if (!activeManagerBucket.value || activeManagerBucket.value === "direct") return [];
  let list = teamGroups.value;
  if (activeManagerBucket.value === "team_incomplete") {
    list = list.filter((t) => !isTeamFullyComplete(t));
  } else if (activeManagerBucket.value === "team_complete") {
    list = list.filter((t) => isTeamFullyComplete(t));
  }
  return list;
});

const rosterDisplayWorkers = computed(() => {
  let list = rosterSource.value;
  if (showManagerBuckets.value && activeManagerBucket.value) {
    if (activeManagerBucket.value === "sanctions") {
      list = sanctionsEvidenceWorkers.value;
    } else if (activeManagerBucket.value === "direct") {
      list = list.filter((w) => isDirectWorker(w));
    } else if (activeTeamLeaderId.value) {
      list = list.filter(
        (w) => w.eval_assignment === "TEAM" && (w.assigned_evaluator_login_id || "").trim() === activeTeamLeaderId.value,
      );
    } else {
      list = [];
    }
  }
  return [...list].sort((a, b) => a.name.localeCompare(b.name, "ko"));
});

/** 평가 화면 — 사이드바 eval_status(미평가·진행중·평가완료)에 맞게 필터 */
const evaluableWorkers = computed(() => {
  let list = isManager.value && evaluator.value?.team_split_active ? workers.value : rosterSource.value;
  if (mainView.value === "evaluate" && activeEvalStatus.value !== "all") {
    list = list.filter((w) => workerEvalStatusKey(w) === activeEvalStatus.value);
  }
  return list;
});

function teamLeaderLabel(loginId: string): string {
  const trimmed = (loginId || "").trim();
  if (!trimmed || trimmed === "미배정") return "미배정";
  const dash = trimmed.indexOf("-");
  return dash >= 0 ? trimmed.slice(dash + 1) : trimmed;
}

function isDirectWorker(w: Worker): boolean {
  return w.eval_assignment === "DIRECT";
}

function isManagerEvaluable(w: Worker): boolean {
  if (!isManager.value || !evaluator.value?.team_split_active) return true;
  return w.eval_assignment === "DIRECT" || w.eval_assignment === "TEAM_LEADER";
}

function selectManagerBucket(bucket: ManagerBucket) {
  activeManagerBucket.value = bucket;
  activeTeamLeaderId.value = null;
}

function selectTeamGroup(leaderLoginId: string) {
  activeTeamLeaderId.value = leaderLoginId;
}

function clearManagerBucketView() {
  activeManagerBucket.value = null;
  activeTeamLeaderId.value = null;
}

function managerBucketBack() {
  if (activeTeamLeaderId.value) {
    activeTeamLeaderId.value = null;
    return;
  }
  clearManagerBucketView();
}

function safetySanctionLineText(w: Worker): string {
  return safetySanctionLine(w);
}

function safetySanctionLineClass(w: Worker): string {
  const cell = safetySanctionDisplay(w);
  const status = (w.sanction_status || "").toUpperCase();
  if (cell.subLabel && (status.includes("PERMANENT") || status.includes("BAN"))) {
    return `${cell.safetyClass} safety-sanction-line safety-sanction-line--ban`;
  }
  return cell.subLabel ? `${cell.safetyClass} safety-sanction-line` : cell.safetyClass;
}

function assignmentLabel(w: Worker): string {
  if (w.eval_assignment_label) return w.eval_assignment_label;
  if (w.eval_assignment === "TEAM") return "팀원";
  if (w.eval_assignment === "TEAM_LEADER") return "팀장";
  return "직영";
}

function canEvaluateWorker(w: Worker): boolean {
  if (period.value?.is_closed) return false;
  return isManagerEvaluable(w);
}

function startEvaluationFromIncomplete() {
  if (!canStartFromIncomplete.value) return;
  const queue = isManager.value && evaluator.value?.team_split_active ? workers.value : rosterSource.value;
  const target = queue.find((w) => isEvalIncomplete(w) && isManagerEvaluable(w));
  if (!target) return;
  startEvaluation(target);
}

function canOpenHistory(w: Worker): boolean {
  if (isManager.value) return true;
  return Boolean(hasActualSanctionHistory(w));
}

function canRegisterSanction(w: Worker): boolean {
  if (w.is_permanently_expelled) return false;
  if (period.value?.is_closed) return true;
  if (evaluationLocked.value) return false;
  return true;
}

function canUploadReward(w: Worker): boolean {
  if (w.is_permanently_expelled) return false;
  if (period.value?.is_closed) {
    if (w.customer_reward) return false;
    return true;
  }
  if (evaluationLocked.value) return false;
  if (w.customer_reward) return false;
  return true;
}

function clearEvidenceThumbCache() {
  evidenceModal.value = null;
  for (const url of Object.values(rewardThumbUrls.value)) {
    URL.revokeObjectURL(url);
  }
  for (const url of Object.values(rewardFullUrls.value)) {
    URL.revokeObjectURL(url);
  }
  for (const url of Object.values(sanctionThumbUrls.value)) {
    URL.revokeObjectURL(url);
  }
  for (const url of Object.values(sanctionFullUrls.value)) {
    URL.revokeObjectURL(url);
  }
  for (const url of Object.values(sanctionSignatureUrls.value)) {
    URL.revokeObjectURL(url);
  }
  rewardThumbUrls.value = {};
  rewardFullUrls.value = {};
  sanctionThumbUrls.value = {};
  sanctionFullUrls.value = {};
  sanctionSignatureUrls.value = {};
}

function isSanctionPhotoEvidence(s: NonNullable<Worker["latest_sanction"]>): boolean {
  return Boolean(s.evidence_photo_url);
}

function sanctionEvidenceKindLabel(s: NonNullable<Worker["latest_sanction"]>): string {
  return isSanctionPhotoEvidence(s) ? "사진" : "텍스트";
}

function workerEvidenceChips(w: Worker): EvidenceChipView[] {
  const chips: EvidenceChipView[] = [];
  if (w.customer_reward?.id) {
    const rewardId = w.customer_reward.id;
    chips.push({
      key: `reward-${rewardId}`,
      tag: "포상",
      kind: "사진",
      tone: "reward",
      title: `${w.name} 포상 근거`,
      thumbUrl: rewardThumbUrls.value[rewardId],
      onClick: () => openRewardEvidenceModal(w.name, rewardId),
    });
  }
  if (w.latest_sanction) {
    const sanction = w.latest_sanction;
    chips.push({
      key: `sanction-${sanction.id}`,
      tag: "제재",
      kind: sanctionEvidenceKindLabel(sanction),
      tone: "sanction",
      title: `${w.name} 제재 근거`,
      thumbUrl: isSanctionPhotoEvidence(sanction) ? sanctionThumbUrls.value[sanction.id] : undefined,
      onClick: () => openSanctionEvidenceModal(w),
    });
  }
  return chips;
}

function closeEvidenceModal() {
  evidenceModal.value = null;
}

function openRewardEvidenceModal(workerName: string, rewardId: number) {
  const open = (photoUrl: string) => {
    evidenceModal.value = {
      title: `${workerName} — 포상 근거`,
      mode: "photo",
      photoUrl,
    };
  };
  const full = rewardFullUrls.value[rewardId];
  if (full) {
    open(full);
    return;
  }
  void ensureRewardThumb(rewardId)
    .then(() => {
      const url = rewardFullUrls.value[rewardId];
      if (url) open(url);
    })
    .catch(() => {
      error.value = "포상 사진을 불러오지 못했습니다.";
    });
}

function openSanctionEvidenceModal(w: Worker) {
  const s = w.latest_sanction;
  if (!s) return;
  const subtitle = [s.violation_label, s.sanction_result_label].filter(Boolean).join(" · ");
  void openSanctionEvidenceModalAsync(w, s, subtitle);
}

async function openSanctionEvidenceModalAsync(
  w: Worker,
  s: NonNullable<Worker["latest_sanction"]>,
  subtitle: string,
) {
  const readOnlyNote = "제재 등록 후 근거·서명은 변경할 수 없습니다.";
  const showSanction = async (photoUrl?: string, signatureUrl?: string) => {
    evidenceModal.value = {
      title: `${w.name} — 제재 근거`,
      subtitle,
      mode: "sanction",
      text: !isSanctionPhotoEvidence(s) ? (s.note || "").trim() || "등록된 코멘트가 없습니다." : undefined,
      photoUrl,
      signatureUrl,
      readOnlyNote,
    };
  };
  let signatureUrl: string | undefined;
  if (s.has_signature) {
    try {
      signatureUrl = await ensureSanctionSignature(s.id);
    } catch {
      signatureUrl = undefined;
    }
  }
  if (isSanctionPhotoEvidence(s)) {
    try {
      await ensureSanctionThumb(s.id);
      await showSanction(sanctionFullUrls.value[s.id], signatureUrl);
    } catch {
      await showSanction(undefined, signatureUrl);
    }
    return;
  }
  await showSanction(undefined, signatureUrl);
}

function blobToThumbUrl(blob: Blob, maxEdge: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const longest = Math.max(img.naturalWidth, img.naturalHeight, 1);
      const scale = Math.min(1, maxEdge / longest);
      const width = Math.max(1, Math.round(img.naturalWidth * scale));
      const height = Math.max(1, Math.round(img.naturalHeight * scale));
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        URL.revokeObjectURL(objectUrl);
        reject(new Error("canvas"));
        return;
      }
      ctx.drawImage(img, 0, 0, width, height);
      URL.revokeObjectURL(objectUrl);
      canvas.toBlob(
        (thumbBlob) => {
          if (!thumbBlob) {
            reject(new Error("thumb"));
            return;
          }
          resolve(URL.createObjectURL(thumbBlob));
        },
        "image/jpeg",
        0.72,
      );
    };
    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error("image"));
    };
    img.src = objectUrl;
  });
}

async function ensureRewardThumb(rewardId: number) {
  if (rewardThumbUrls.value[rewardId] && rewardFullUrls.value[rewardId]) return;
  const res = await api.get(`/functional-eval/customer-rewards/${rewardId}/photo`, { responseType: "blob" });
  const full = URL.createObjectURL(res.data);
  const thumb = await blobToThumbUrl(res.data, EVIDENCE_THUMB_MAX_EDGE);
  rewardFullUrls.value = { ...rewardFullUrls.value, [rewardId]: full };
  rewardThumbUrls.value = { ...rewardThumbUrls.value, [rewardId]: thumb };
}

async function ensureSanctionSignature(sanctionId: number) {
  if (sanctionSignatureUrls.value[sanctionId]) return sanctionSignatureUrls.value[sanctionId];
  const res = await api.get(`/functional-eval/sanctions/${sanctionId}/signature`, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  sanctionSignatureUrls.value = { ...sanctionSignatureUrls.value, [sanctionId]: url };
  return url;
}

async function ensureSanctionThumb(sanctionId: number) {
  if (sanctionThumbUrls.value[sanctionId] && sanctionFullUrls.value[sanctionId]) return;
  const res = await api.get(`/functional-eval/sanctions/${sanctionId}/evidence-photo`, { responseType: "blob" });
  const full = URL.createObjectURL(res.data);
  const thumb = await blobToThumbUrl(res.data, EVIDENCE_THUMB_MAX_EDGE);
  sanctionFullUrls.value = { ...sanctionFullUrls.value, [sanctionId]: full };
  sanctionThumbUrls.value = { ...sanctionThumbUrls.value, [sanctionId]: thumb };
}

async function preloadRewardThumbs(rows: Worker[]) {
  const ids = [
    ...new Set(
      rows.map((w) => w.customer_reward?.id).filter((id): id is number => typeof id === "number"),
    ),
  ];
  await Promise.all(
    ids.map(async (id) => {
      try {
        await ensureRewardThumb(id);
      } catch {
        /* ignore missing photo */
      }
    }),
  );
}

async function preloadSanctionThumbs(rows: Worker[]) {
  const ids = [
    ...new Set(
      rows
        .map((w) => (w.latest_sanction?.evidence_photo_url ? w.latest_sanction.id : null))
        .filter((id): id is number => typeof id === "number"),
    ),
  ];
  await Promise.all(
    ids.map(async (id) => {
      try {
        await ensureSanctionThumb(id);
      } catch {
        /* ignore missing photo */
      }
    }),
  );
}

async function preloadEvidenceThumbs(rows: Worker[]) {
  await Promise.all([preloadRewardThumbs(rows), preloadSanctionThumbs(rows)]);
}

function scheduleEvidenceThumbPreload(rows: Worker[]) {
  const run = () => void preloadEvidenceThumbs(rows);
  if (typeof window !== "undefined" && "requestIdleCallback" in window) {
    window.requestIdleCallback(run, { timeout: 4000 });
  } else {
    window.setTimeout(run, 2000);
  }
}

let evalCatalogPromise: Promise<void> | null = null;
let violationCatalogPromise: Promise<void> | null = null;

async function ensureEvalCatalog() {
  if (evalCatalog.value) return;
  if (!evalCatalogPromise) {
    evalCatalogPromise = loadEvalCatalog().catch((e) => {
      evalCatalogPromise = null;
      throw e;
    });
  }
  await evalCatalogPromise;
}

async function ensureViolationCatalog() {
  if (violations.value.length) return;
  if (!violationCatalogPromise) {
    violationCatalogPromise = loadCatalog().catch((e) => {
      violationCatalogPromise = null;
      throw e;
    });
  }
  await violationCatalogPromise;
}

const groupedViolations = computed(() => {
  const map = new Map<string, { category: string; label: string; items: ViolationItem[] }>();
  for (const item of violations.value) {
    if (!map.has(item.category)) {
      map.set(item.category, { category: item.category, label: item.category_label, items: [] });
    }
    map.get(item.category)!.items.push(item);
  }
  return Array.from(map.values());
});

const allHistorySanctions = computed(() => {
  if (!historyData.value?.history_visible) return [];
  return [...(historyData.value.prior_sanctions || []), ...(historyData.value.sanctions || [])];
});

const allHistoryAssessments = computed(() => {
  if (!historyData.value?.history_visible) return [];
  return historyData.value.prior_assessments || [];
});

const historyAdjustments = computed(() => {
  const adj = historyData.value?.adjustments || historyData.value?.mileage || {};
  const penalty = Number(adj.penalty_points ?? 0);
  const bonus = Number(adj.bonus_points ?? 0);
  return {
    penalty_points: penalty,
    bonus_points: bonus,
    penalty_label: adj.penalty_label || (penalty > 0 ? `감점 -${penalty}점` : ""),
    bonus_label: adj.bonus_label || (bonus > 0 ? `가점 +${bonus}점` : ""),
  };
});

const dialogShellClass = computed(() =>
  isMobileViewport.value ? "fe-sheet fe-sheet-open" : "fe-modal-panel",
);

function statusClass(status: string) {
  if (status.includes("EXPULSION") || status.includes("BAN")) return "danger";
  if (status.includes("WARNING") || status.includes("TRAINING")) return "warn";
  return "normal";
}

function sanctionHistoryLabel(s: SanctionRow): string {
  return s.sanction_display_label || s.outcome_label || s.institutional_sanction_label || s.sanction_result_label;
}

function sanctionOutcomeClass(s: SanctionRow): string {
  if (s.is_hiring_ban) return "sanction-outcome sanction-outcome--ban";
  const label = s.outcome_label || s.institutional_sanction_label || "";
  if (label === "현장퇴출") return "sanction-outcome sanction-outcome--expulsion";
  return "sanction-outcome";
}


function closePanels() {
  closeForm();
  closeHistory();
  closeRewardUpload();
}

function onSanctionFormSaved() {
  sanctionPromptMessage.value = "";
  closeForm();
  flashSaveNotice(
    period.value?.is_closed
      ? "제재 이력이 제출되었습니다. 본사 승인 후 반영됩니다."
      : "제재가 등록되었습니다.",
  );
  void load();
}

async function previewSanctionEvidence(sanctionId: number, workerName = "근로자", subtitle = "") {
  try {
    await ensureSanctionThumb(sanctionId);
    const url = sanctionFullUrls.value[sanctionId];
    if (!url) throw new Error("missing");
    evidenceModal.value = {
      title: `${workerName} — 제재 근거`,
      subtitle: subtitle || undefined,
      mode: "photo",
      photoUrl: url,
    };
  } catch {
    error.value = "근거 사진을 불러오지 못했습니다.";
  }
}

function openSanctionTextFromHistory(workerName: string, s: SanctionRow) {
  evidenceModal.value = {
    title: `${workerName} — 제재 근거`,
    subtitle: [s.violation_label, s.institutional_sanction_label || s.sanction_result_label].filter(Boolean).join(" · "),
    mode: "text",
    text: (s.note || "").trim() || "등록된 코멘트가 없습니다.",
  };
}

function workerEvalStatus(w: Worker): string {
  if (isFullyComplete(w)) return "완료";
  if (isFunctionalComplete(w) || isSafetyComplete(w)) return "진행중";
  return "미완료";
}

function workerEvalStatusKey(w: Worker): EvalStatusKey {
  return evalStatusFromLabel[workerEvalStatus(w)] ?? "incomplete";
}

function rosterStatusLabel(w: Worker): string {
  const status = workerEvalStatus(w);
  if (status === "진행중") return "진행";
  if (status === "미완료") return "대기";
  return "완료";
}

function rosterStatusClass(w: Worker): string {
  if (workerEvalStatus(w) === "완료") return "done";
  if (workerEvalStatus(w) === "진행중") return "normal";
  return "pending";
}

function flashSaveNotice(message: string, durationMs = 2800) {
  saveNotice.value = message;
  if (saveNoticeTimer) clearTimeout(saveNoticeTimer);
  saveNoticeTimer = setTimeout(() => {
    saveNotice.value = "";
    saveNoticeTimer = null;
  }, durationMs);
}

function evalQueue(): Worker[] {
  const list = isManager.value && evaluator.value?.team_split_active ? workers.value : rosterSource.value;
  return [...list].sort((a, b) => a.name.localeCompare(b.name, "ko"));
}

async function advanceToNextWorker(afterId: number) {
  await load();
  const next = findNextIncompleteWorker(evalQueue(), afterId);
  if (!next) {
    flashSaveNotice("모든 근로자 평가가 완료되었습니다. 현황으로 이동합니다.");
    window.setTimeout(() => void goToRoster(), 900);
    return;
  }
  focusWorkerId.value = next.id;
  activeTab.value = isFunctionalComplete(next) ? "safety" : "functional";
  const phase = isFunctionalComplete(next) ? "안전" : "기능";
  flashSaveNotice(`${next.name}님 ${phase} 평가를 시작합니다.`);
}

async function goToRoster() {
  await load();
  clearManagerBucketView();
  await router.push({ name: "site-functional-eval" });
  focusWorkerId.value = null;
  saveNotice.value = "";
}

function startEvaluation(worker?: Worker) {
  void ensureEvalCatalog();
  const target = (() => {
    if (worker) {
      if (!isManagerEvaluable(worker)) return null;
      return worker;
    }
    const queue = isManager.value && evaluator.value?.team_split_active ? workers.value : rosterSource.value;
    const firstIncomplete = queue.find((w) => isEvalIncomplete(w) && isManagerEvaluable(w));
    if (firstIncomplete) return firstIncomplete;
    return queue.find((w) => isManagerEvaluable(w)) ?? null;
  })();
  if (!target) return;

  evalSessionKey.value += 1;
  focusWorkerId.value = target.id;
  activeTab.value = isFunctionalComplete(target) ? "safety" : "functional";
  const nextRoute = { name: "site-functional-eval-evaluate" as const };

  if (route.name === "site-functional-eval-evaluate") {
    void router.replace(nextRoute);
    return;
  }
  void router.push(nextRoute);
}

function onRosterStatusClick(w: Worker) {
  if (!canEvaluateWorker(w)) return;
  if (workerEvalStatusKey(w) === "complete") return;
  startEvaluation(w);
}

async function onRevisionSaved(worker: Worker) {
  await load();
  flashSaveNotice(`${worker.name}님 평가 수정이 저장되었습니다.`);
}

async function onSafetySaved(worker: Worker) {
  await load();
  const fresh = rosterSource.value.find((w) => w.id === worker.id) ?? workers.value.find((w) => w.id === worker.id) ?? worker;
  flashSaveNotice(`${fresh.name}님 안전 평가가 저장되었습니다.`);

  const prefill = buildSanctionPrefillFromSafetyScores(
    fresh.safety_assessment?.scores || {},
    evalCriteria.value,
  );
  if (prefill) {
    form.violation_code = prefill.violationCode;
    form.note = prefill.note;
    sanctionFormKey.value += 1;
  }

  if (needsSanctionPrompt(fresh)) {
    sanctionPromptMessage.value =
      "「문제」로 평가한 항목이 선택되었습니다. 근거 코멘트를 확인·보완한 뒤 제재를 등록하세요.";
    focusWorkerId.value = fresh.id;
    activeTab.value = "safety";
    if (isMobileViewport.value) {
      openSanction(fresh);
    }
    return;
  }
  await advanceToNextWorker(fresh.id);
}

function onRequestSafety(workerId: number) {
  const worker = rosterSource.value.find((w) => w.id === workerId);
  focusWorkerId.value = workerId;
  activeTab.value = "safety";
  flashSaveNotice(
    worker ? `${worker.name}님 기능 평가 저장 · 안전평가로 이동합니다.` : "기능 평가 저장 · 안전평가로 이동합니다.",
  );
}

async function onSanctionRegistered() {
  sanctionPromptMessage.value = "";
  const workerId = focusWorkerId.value;
  if (workerId == null) return;
  await load();
  flashSaveNotice("제재가 등록되었습니다.");
  await advanceToNextWorker(workerId);
}

async function onRewardRegistered() {
  await load();
  flashSaveNotice("포상 사진이 제출되었습니다. 본사 승인을 기다립니다.");
}

watch(activeTab, (tab) => {
  closeForm();
  closeHistory();
  if (tab === "safety") void ensureViolationCatalog();
});

watch(mainView, (view) => {
  if (view === "roster") {
    sanctionPromptMessage.value = "";
  }
});

function openHistoryById(workerId: number) {
  const worker = rosterSource.value.find((w) => w.id === workerId);
  if (worker) openHistory(worker);
}

async function loadCatalog() {
  const res = await api.get("/functional-eval/violation-catalog");
  violations.value = res.data.items || [];
  const defaultCode = res.data.default_violation_code as string | undefined;
  if (defaultCode) {
    form.violation_code = defaultCode;
  } else if (violations.value.length && !form.violation_code) {
    form.violation_code = violations.value[0].code;
  }
}

function openRewardUpload(w: Worker) {
  closeForm();
  closeHistory();
  rewardWorker.value = w;
  rewardReadOnly.value = false;
  rewardPhotoFile.value = null;
  rewardError.value = "";
  if (rewardPreviewUrl.value) {
    URL.revokeObjectURL(rewardPreviewUrl.value);
    rewardPreviewUrl.value = null;
  }
  if (rewardPhotoInput.value) rewardPhotoInput.value.value = "";
  void loadRewardHistory(w.id);
}

function closeRewardUpload() {
  rewardWorker.value = null;
  rewardReadOnly.value = false;
  rewardPhotoFile.value = null;
  rewardError.value = "";
  rewardHistory.value = [];
  if (rewardPreviewUrl.value) {
    URL.revokeObjectURL(rewardPreviewUrl.value);
    rewardPreviewUrl.value = null;
  }
}

function rewardStatusLabel(status: string): string {
  if (status === "APPROVED") return "승인";
  if (status === "PENDING") return "승인 대기";
  if (status === "REJECTED") return "반려";
  return status;
}

async function loadRewardHistory(workerId: number) {
  try {
    const res = await api.get(`/functional-eval/workers/${workerId}/customer-rewards`);
    rewardHistory.value = res.data.items || [];
  } catch {
    rewardHistory.value = [];
  }
}

async function previewRewardPhoto(rewardId: number) {
  try {
    await ensureRewardThumb(rewardId);
    openRewardEvidenceModal("근로자", rewardId);
  } catch {
    rewardError.value = "사진을 불러오지 못했습니다.";
  }
}

function onRewardPhotoChange(e: Event) {
  const input = e.target as HTMLInputElement;
  rewardPhotoFile.value = input.files?.[0] ?? null;
  if (rewardPreviewUrl.value) {
    URL.revokeObjectURL(rewardPreviewUrl.value);
    rewardPreviewUrl.value = null;
  }
  if (rewardPhotoFile.value) {
    rewardPreviewUrl.value = URL.createObjectURL(rewardPhotoFile.value);
  }
}

async function submitRewardUpload() {
  if (!rewardWorker.value || !rewardPhotoFile.value) return;
  const workerName = rewardWorker.value.name;
  rewardUploading.value = true;
  rewardError.value = "";
  try {
    const fd = new FormData();
    fd.append("photo", rewardPhotoFile.value);
    await api.post(`/functional-eval/workers/${rewardWorker.value.id}/customer-rewards`, fd, {
      params: { bonus_points: 5 },
      headers: { "Content-Type": "multipart/form-data" },
    });
    closeRewardUpload();
    flashSaveNotice(`${workerName}님 포상 사진이 제출되었습니다. 본사 승인을 기다립니다.`);
    await load();
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    rewardError.value = typeof detail === "string" ? detail : "포상 사진 제출에 실패했습니다.";
  } finally {
    rewardUploading.value = false;
  }
}

function cloneWorkerList(rows: Worker[]): Worker[] {
  return (rows || []).map((w) => ({
    ...w,
    functional_assessment: w.functional_assessment ? { ...w.functional_assessment } : w.functional_assessment,
    safety_assessment: w.safety_assessment ? { ...w.safety_assessment } : w.safety_assessment,
  }));
}

async function load() {
  error.value = "";
  attendanceMessage.value = "";
  clearEvidenceThumbCache();
  try {
    const res = await api.get("/functional-eval/my-site/workers");
    period.value = res.data.period;
    workers.value = cloneWorkerList(res.data.items || []);
    siteOverview.value = cloneWorkerList(res.data.site_overview || []);
    approval.value = res.data.approval ? { ...res.data.approval } : null;
    teamSignoff.value = res.data.team_signoff ? { ...res.data.team_signoff } : null;
    mySignatures.value = res.data.signatures || [];
    evaluator.value = res.data.evaluator || null;
    attendanceMessage.value = res.data.attendance_message || "";
    syncFeSiteSession();
    maybeAutoRouteTeamLeader();

    void api
      .get("/functional-eval/my-site/grade-stats")
      .then((statsRes) => {
        siteGradeStats.value = statsRes.data;
      })
      .catch(() => {
        siteGradeStats.value = null;
      });

    const thumbSources = [...workers.value, ...siteOverview.value];
    scheduleEvidenceThumbPreload(thumbSources);
  } catch (e: unknown) {
    workers.value = [];
    siteOverview.value = [];
    siteGradeStats.value = null;
    syncFeSiteSession();
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value =
      typeof msg === "string"
        ? msg
        : "근로자 목록을 불러오지 못했습니다. 서버·DB 마이그레이션(0068·0069)을 확인하세요.";
  }
  applyGuidePreviewScene();
}

function syncFeSiteSession() {
  const role: "MANAGER" | "TEAM_LEADER" | null = evaluator.value
    ? evaluator.value.role === "MANAGER"
      ? "MANAGER"
      : "TEAM_LEADER"
    : null;
  const loginId = (auth.user?.login_id || "").trim();
  feSiteSession.syncFromSite(role, isTeamLeaderFlow.value ? teamLeaderPhase.value : null, loginId || null);
}

function maybeAutoRouteTeamLeader() {
  if (isFeGuidePreview()) return;
  if (isManager.value || !evaluator.value || period.value?.is_closed) return;
  const stepQuery = typeof route.query.team_step === "string" ? route.query.team_step : "";
  if (stepQuery === "results" || stepQuery === "report") return;
  if (teamLeaderPhase.value === "evaluate" && mainView.value === "roster" && evaluableIncompleteCount.value > 0) {
    startEvaluation();
    return;
  }
  if (teamLeaderPhase.value === "report" && mainView.value === "evaluate") {
    void goToRoster();
  }
}

function applyGuidePreviewScene() {
  if (!isFeGuidePreview()) return;
  if (getFeGuideScene() === "reward-upload") {
    const candidate =
      workers.value.find((w) => canUploadReward(w)) ??
      workers.value[0] ??
      ({
        id: 0,
        row_no: 1,
        name: "김양호",
        sanction_status: "NONE",
        sanction_status_label: "없음",
        is_permanently_expelled: false,
        history_visible: true,
      } as Worker);
    openRewardUpload(candidate);
    return;
  }
  if (getFeGuideScene() === "team-signoff") {
    signatureModalMode.value = "team";
    signatureModalOpen.value = true;
  }
}

function openTeamSignoffModal() {
  signatureModalMode.value = "team";
  signatureModalOpen.value = true;
}

function openSiteApprovalModal() {
  signatureModalMode.value = "site";
  signatureModalOpen.value = true;
}

async function rejectTeamReport(loginId: string, name: string) {
  const rejectNote = window.prompt(`${name} 팀장 평가를 반려합니다. 사유(선택):`) ?? "";
  if (rejectNote === null) return;
  rejectingTeamReport.value = true;
  error.value = "";
  try {
    await api.post(
      `/functional-eval/my-site/team-leader/${encodeURIComponent(loginId)}/reject-report`,
      { reject_note: rejectNote },
    );
    flashSaveNotice(`${name} 팀장 평가가 반려되었습니다. 팀장이 점수를 수정한 뒤 다시 서명합니다.`);
    await load();
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof msg === "string" ? msg : "반려 처리에 실패했습니다.";
  } finally {
    rejectingTeamReport.value = false;
  }
}

async function onSignatureModalSubmit(payload: {
  signature_data: string;
  consent_acknowledged: boolean;
  s_over_limit_reason?: string;
  no_c_grade_reason?: string;
}) {
  signatureModalRef.value?.setSubmitting(true);
  error.value = "";
  try {
    if (signatureModalMode.value === "team") {
      submittingTeamSignoff.value = true;
      await api.post("/functional-eval/my-team/signoff", payload);
    } else {
      submittingApproval.value = true;
      await api.post("/functional-eval/my-site/approval/submit", payload);
    }
    signatureModalOpen.value = false;
    await load();
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    signatureModalRef.value?.setError(typeof msg === "string" ? msg : "서명 저장에 실패했습니다.");
  } finally {
    submittingApproval.value = false;
    submittingTeamSignoff.value = false;
    signatureModalRef.value?.setSubmitting(false);
  }
}

async function downloadSignatureDoc(signatureId: number) {
  try {
    const res = await api.get(`/functional-eval/signatures/${signatureId}/document`, { responseType: "blob" });
    downloadBlobAsFile(res.data, `기능인제_서명_${signatureId}.pdf`, res.headers);
  } catch {
    error.value = "서명본 다운로드에 실패했습니다.";
  }
}

async function downloadConsentDoc() {
  try {
    const res = await api.get("/functional-eval/consent/document", { responseType: "blob" });
    downloadBlobAsFile(res.data, "기능인제_동의서.pdf", res.headers);
  } catch {
    error.value = "동의서 다운로드에 실패했습니다.";
  }
}

async function submitSiteApproval() {
  openSiteApprovalModal();
}

function siteGradeWorkbookFilename() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `현장별 기능인등급-${y}${m}${day}.xlsx`;
}

async function downloadSiteGradeWorkbook() {
  exportingGrade.value = true;
  error.value = "";
  try {
    const res = await api.get("/functional-eval/my-site/export/site-grade-workbook", { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = siteGradeWorkbookFilename();
    a.click();
    URL.revokeObjectURL(url);
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = typeof msg === "string" ? msg : "엑셀 출력에 실패했습니다.";
  } finally {
    exportingGrade.value = false;
  }
}

async function openHistory(worker: Worker) {
  selectedWorker.value = null;
  error.value = "";
  historyWorker.value = worker;
  historyData.value = null;
  document.body.classList.add("fe-sheet-open-body");
  try {
    const res = await api.get(`/functional-eval/workers/${worker.id}/history`);
    historyData.value = res.data;
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    historyData.value = {
      history_visible: false,
      message: typeof msg === "string" ? msg : "이력을 불러오지 못했습니다.",
      sanctions: [],
      prior_sanctions: [],
      prior_assessments: [],
      adjustments: {},
    };
  }
}

async function openSanction(worker: Worker) {
  await Promise.all([ensureViolationCatalog(), ensureEvalCatalog()]);
  historyWorker.value = null;
  historyData.value = null;
  selectedWorker.value = worker;
  error.value = "";
  const prefill = buildSanctionPrefillFromSafetyScores(
    worker.safety_assessment?.scores || {},
    evalCriteria.value,
  );
  if (prefill) {
    form.violation_code = prefill.violationCode;
    form.note = prefill.note;
    sanctionFormKey.value += 1;
  } else if (!form.violation_code && violations.value.length) {
    form.note = "";
  }
  document.body.classList.add("fe-sheet-open-body");
}

function closeForm() {
  selectedWorker.value = null;
  error.value = "";
  sanctionPromptMessage.value = "";
  document.body.classList.remove("fe-sheet-open-body");
}

function closeHistory() {
  historyWorker.value = null;
  historyData.value = null;
  error.value = "";
  document.body.classList.remove("fe-sheet-open-body");
}

async function loadEvalCatalog() {
  const res = await api.get("/functional-eval/eval-catalog");
  evalCatalog.value = res.data;
}

onMounted(() => {
  void load();
});

watch(
  () => mainView.value,
  (view) => {
    if (view === "evaluate") void ensureEvalCatalog();
  },
  { immediate: true },
);

watch(
  () => route.query.team_step,
  (step) => {
    if (!isTeamLeaderFlow.value || typeof step !== "string") return;
    if (step === "report" && teamLeaderPhase.value !== "evaluate" && mainView.value === "evaluate") {
      void goToRoster();
    }
  },
);

watch(
  () => route.query.guideScene,
  () => {
    applyGuidePreviewScene();
  },
);

onBeforeUnmount(() => {
  clearEvidenceThumbCache();
});
</script>

<style scoped>
.attendance-warn {
  margin: 8px 0 0;
  padding: 10px 12px;
  background: #fff7ed;
  border: 1px solid #fdba74;
  border-radius: 8px;
  color: #9a3412;
  font-size: 14px;
}

.load-error {
  margin: 8px 0 0;
  padding: 10px 12px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #991b1b;
  font-size: 14px;
}

.fe-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

.team-leader-stepbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
}

.team-step {
  flex: 1 1 calc(50% - 8px);
  min-width: 120px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
  font-size: 15px;
  font-weight: 600;
  color: #64748b;
  text-align: center;
}

.team-step--active {
  border-color: #ea580c;
  background: #fff7ed;
  color: #c2410c;
}

.team-step--done {
  border-color: #86efac;
  background: #f0fdf4;
  color: #166534;
}

.team-leader-panel-title {
  margin: 0 0 8px;
  font-size: 1.35rem;
  color: #0f172a;
}

.team-leader-panel-desc {
  margin: 0 0 16px;
  font-size: 17px;
  line-height: 1.55;
  color: #475569;
}

.team-leader-report-panel,
.team-leader-results-head {
  margin-bottom: 12px;
}

.approval-panel--team-leader {
  padding: 16px;
  border-radius: 12px;
  background: #fffbeb;
  border: 1px solid #fcd34d;
}

.approval-panel--team-leader .btn-approve-site {
  width: 100%;
  max-width: 420px;
  font-size: 19px;
  min-height: 56px;
}

@media (min-width: 769px) {
  .team-step {
    flex: 1 1 auto;
    font-size: 16px;
  }

  /* 데스크톱은 사이드바 단계 메뉴 사용 — 상단 stepbar 중복 숨김 */
  .team-leader-stepbar {
    display: none;
  }
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.page-head-text {
  min-width: 0;
}

.page-title {
  margin: 0;
  font-size: 1.25rem;
}

.page-sub {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 13px;
}

.badge {
  margin-left: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  vertical-align: middle;
}

.badge.open {
  background: #dcfce7;
  color: #166534;
}

.badge.closed {
  background: #fee2e2;
  color: #991b1b;
}

.incomplete-count {
  margin-left: 10px;
  font-size: 13px;
  font-weight: 600;
  color: #b45309;
  border: none;
  padding: 0;
  background: transparent;
  cursor: pointer;
  text-decoration: underline;
  line-height: 1.2;
}

.incomplete-count:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  text-decoration: none;
}

.evaluator-badge {
  display: inline-block;
  margin-right: 8px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  vertical-align: middle;
}

.evaluator-badge--manager {
  background: #dbeafe;
  color: #1d4ed8;
}

.evaluator-badge--leader {
  background: #e0e7ff;
  color: #4338ca;
}

.evaluator-hint {
  margin: 8px 0 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.45;
}

.page-head-actions {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-refresh,
.btn-export {
  flex-shrink: 0;
}

.panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px;
}

.field {
  display: block;
  margin-top: 12px;
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 6px;
}

.field-control {
  width: 100%;
  box-sizing: border-box;
  font-size: 16px;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
}

select.field-control {
  min-height: 48px;
}

textarea.field-control {
  resize: vertical;
  min-height: 80px;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.actions-sticky {
  position: sticky;
  bottom: 0;
  padding-bottom: env(safe-area-inset-bottom, 0);
  background: linear-gradient(transparent, #fff 12px);
}

.touch-btn {
  flex: 1;
  min-height: 48px;
  font-size: 15px;
}

.touch-btn-inline {
  min-height: 44px;
  padding: 8px 12px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  border-bottom: 1px solid #e5e7eb;
  padding: 10px 8px;
  text-align: left;
}

.actions-cell {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.status-cell {
  white-space: nowrap;
  min-width: 72px;
}

.col-status {
  white-space: nowrap;
  min-width: 72px;
}

.status-locked-hint {
  display: block;
  margin-top: 4px;
  font-size: 11px;
}

.status-pill--compact {
  padding: 2px 8px;
  font-size: 11px;
}

.status-pill {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.status-pill-link {
  border: none;
  background: transparent;
  cursor: pointer;
}

.status-pill-link:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.status-pill.danger {
  background: #fee2e2;
  color: #991b1b;
}

.status-pill.warn {
  background: #fef3c7;
  color: #92400e;
}

.status-pill.normal {
  background: #f1f5f9;
  color: #475569;
}

.status-pill.done {
  background: #dcfce7;
  color: #166534;
}

.status-pill.pending {
  background: #fef3c7;
  color: #92400e;
}

.fe-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.fe-tab {
  flex: 1;
  min-width: 100px;
  min-height: 44px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  color: #334155;
  white-space: nowrap;
}

.fe-tab.active {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.fe-tab-back {
  flex: 0 0 auto;
  min-width: auto;
  padding: 0 14px;
  background: #f8fafc;
}

.save-notice {
  margin: 0 0 12px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #ecfdf5;
  border: 1px solid #6ee7b7;
  color: #065f46;
  font-size: 14px;
  font-weight: 600;
}

.roster-table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.site-grade-stats-panel {
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}
.roster-panel {
  padding: 16px;
}

.roster-toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.roster-search {
  flex: 1;
  min-width: 160px;
}

.btn-start-eval {
  min-height: 44px;
  white-space: nowrap;
}

.roster-table-wrap .data-table tbody tr.row-highlight--alert {
  background: #fef2f2;
}

.roster-table-wrap .data-table tbody tr.row-highlight--alert:hover {
  background: #fee2e2;
}

.history-sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.history-block h3 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #334155;
}

.roster-desc {
  margin: 10px 0 14px;
  font-size: 13px;
  color: #64748b;
}

.signatures-panel {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}
.signatures-title { margin: 0 0 8px; font-size: 14px; }
.signatures-list { margin: 0; padding-left: 18px; }
.signatures-list li { display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }

.approval-panel {
  margin-bottom: 14px;
  padding: 12px 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.team-report-list {
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}

.team-report-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 10px 0;
  border-top: 1px solid #e2e8f0;
}

.team-report-hint {
  margin: 0;
  font-size: 12px;
}

.team-report-actions {
  display: flex;
  gap: 8px;
  width: 100%;
}

.danger-outline {
  border-color: #fca5a5;
  color: #b91c1c;
}

.approval-stats {
  font-size: 13px;
  color: #334155;
  font-weight: 600;
}

.approval-status {
  margin: 8px 0 10px;
  font-size: 13px;
  color: #64748b;
}

.btn-approve-site {
  min-height: 44px;
}

.muted-action {
  font-size: 12px;
  color: #94a3b8;
}

.col-remark,
.remark-cell {
  max-width: 220px;
  font-size: 13px;
  color: #475569;
  line-height: 1.35;
  word-break: keep-all;
}

.safety-sanction-cell {
  white-space: nowrap;
  min-width: 88px;
}

.col-safety-sanction {
  white-space: nowrap;
  min-width: 108px;
}

.safety-sanction-line,
.safety-sanction-cell .grade-pill {
  white-space: nowrap;
}

.safety-sanction-line--ban {
  color: #dc2626;
  font-weight: 600;
}

.manager-bucket-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

@media (min-width: 900px) {
  .manager-bucket-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

.bucket-grid .bucket-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 16px 14px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: box-shadow 0.15s, border-color 0.15s;
}

.bucket-grid .bucket-card:hover {
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
}

.bucket-card--direct { border-top: 4px solid #2563eb; }
.bucket-card--leaders { border-top: 4px solid #7c3aed; }
.bucket-card--pending { border-top: 4px solid #ea580c; }
.bucket-card--done { border-top: 4px solid #16a34a; }

.bucket-card__label { font-size: 14px; font-weight: 600; color: #0f172a; }
.bucket-card__count { font-size: 28px; font-weight: 700; color: #0f172a; line-height: 1; }
.bucket-card__hint { font-size: 12px; color: #64748b; }

.bucket-list-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.bucket-list-title {
  margin: 0;
  font-size: 17px;
}

.team-group-list {
  list-style: none;
  margin: 0 0 14px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.team-group-list .site-list-item {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  text-align: left;
}

.team-group-list .site-list-item:hover {
  background: #f8fafc;
}

.team-group-list .site-list-item__main {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.team-group-list .progress-bar {
  width: 72px;
  height: 6px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
}

.team-group-list .progress-bar__fill {
  height: 100%;
  background: #2563eb;
  border-radius: 999px;
}

.empty-bucket {
  padding: 16px 0;
  text-align: center;
}

.roster-table .grade-pill {
  display: inline-block;
  min-width: 28px;
  text-align: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}

.grade-pill--pending {
  background: #fef3c7;
  color: #92400e;
}

.grade-pill--s {
  background: #dcfce7;
  color: #166534;
}

.grade-pill--a {
  background: #dbeafe;
  color: #1d4ed8;
}

.grade-pill--b {
  background: #e0e7ff;
  color: #4338ca;
}

.grade-pill--c {
  background: #ffedd5;
  color: #c2410c;
}

.grade-pill--d {
  background: #fee2e2;
  color: #991b1b;
}

.roster-grades {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.roster-grades .grade-pill {
  font-size: 12px;
  padding: 3px 8px;
}

.req {
  color: #dc2626;
}

.history-note {
  display: block;
  margin-top: 2px;
}

.sanction-hint {
  margin: 8px 0 0;
  padding: 10px 12px;
  background: #fff7ed;
  border: 1px solid #fdba74;
  border-radius: 8px;
  color: #9a3412;
  font-size: 13px;
  line-height: 1.45;
}

.reward-history {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.reward-history li {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.reward-status {
  font-weight: 600;
  color: #0f172a;
}

.reward-preview {
  margin-top: 10px;
}

.reward-preview img {
  max-width: 100%;
  max-height: 220px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  object-fit: contain;
  background: #f8fafc;
}

.evidence-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  width: 100%;
}

.evidence-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px 3px 4px;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  cursor: pointer;
  font-size: 11px;
  line-height: 1.2;
}

.evidence-chip--reward {
  border-color: #93c5fd;
  background: #eff6ff;
}

.evidence-chip--sanction {
  border-color: #fdba74;
  background: #fff7ed;
}

.evidence-chip__tag {
  font-weight: 700;
  color: #0f172a;
}

.evidence-chip__kind {
  color: #475569;
}

.evidence-chip__thumb {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  object-fit: cover;
  border: 1px solid rgba(15, 23, 42, 0.08);
}

.evidence-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.55);
}

.evidence-modal {
  width: min(560px, 100%);
  max-height: calc(100vh - 40px);
  overflow: auto;
  margin: 0;
}

.evidence-modal-subtitle {
  margin: 0 0 12px;
  font-size: 13px;
  color: #64748b;
}

.evidence-modal-photo {
  display: block;
  width: 100%;
  max-height: min(70vh, 640px);
  object-fit: contain;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.evidence-modal-text {
  margin: 0;
  padding: 12px 14px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  white-space: pre-wrap;
  line-height: 1.5;
}

.evidence-modal-signature {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.evidence-modal-signature-label {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #1e3a5f;
}

.evidence-modal-signature-img {
  display: block;
  max-width: 280px;
  max-height: 100px;
  border: 1px dashed #cbd5e1;
  background: #f8fafc;
}

.evidence-modal-readonly {
  margin: 12px 0 0;
  font-size: 12px;
  color: #b45309;
  font-weight: 600;
}

.eval-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.eval-actions .full-width {
  grid-column: 1 / -1;
}

.error {
  color: #b91c1c;
  margin-top: 8px;
}

.history-list {
  padding-left: 18px;
  font-size: 14px;
  margin: 12px 0 0;
}

.sanction-outcome {
  font-weight: 600;
}

.sanction-outcome--ban {
  color: #dc2626;
}

.sanction-outcome--expulsion {
  color: #ea580c;
}

.history-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.history-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.points-box {
  margin-top: 16px;
  padding: 12px;
  background: #f1f5f9;
  border-radius: 8px;
}

.points-box h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.points-line {
  margin: 4px 0;
  font-size: 14px;
}

.points-line--penalty {
  color: #991b1b;
  font-weight: 600;
}

.points-line--bonus {
  color: #065f46;
  font-weight: 600;
}

.mileage-box {
  margin-top: 16px;
  padding: 12px;
  background: #f1f5f9;
  border-radius: 8px;
}

.mileage-box h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.tag {
  font-size: 11px;
  background: #e2e8f0;
  padding: 1px 6px;
  border-radius: 4px;
  margin-right: 4px;
}

.warn {
  color: #991b1b;
}

.meta {
  color: #64748b;
  font-size: 12px;
  display: block;
  margin-top: 4px;
}

.workers-head {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}

.workers-head h2 {
  margin: 0;
  font-size: 1.05rem;
}

.count {
  color: #64748b;
  font-weight: 500;
}

.worker-search {
  max-width: 100%;
}

.table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.empty-cell {
  text-align: center;
  color: #64748b;
  padding: 24px;
}

.desktop-only {
  display: block;
}

.mobile-only {
  display: none;
}

.worker-cards {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.worker-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  background: #fafafa;
}

.worker-card-main {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.worker-no {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e2e8f0;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}

.worker-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.worker-name {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.worker-card-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 12px;
}

.card-btn {
  min-height: 44px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
}

.card-btn-secondary {
  background: #fff;
  border-color: #cbd5e1;
  color: #334155;
}

.card-btn-primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.card-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.empty-card {
  text-align: center;
  color: #64748b;
  background: #fff;
}

.link-btn {
  background: none;
  border: none;
  color: #2563eb;
  cursor: pointer;
  font-size: 14px;
  padding: 4px 0;
}

@media (max-width: 768px) {
  .desktop-only {
    display: none;
  }

  .mobile-only {
    display: flex;
  }

  .page-head--mobile {
    gap: 8px;
  }

  .page-head--mobile .page-sub {
    margin-top: 0;
    font-size: 12px;
    line-height: 1.45;
  }

  .page-head-actions--mobile {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    width: 100%;
  }

  .page-head-actions--mobile .btn-export,
  .page-head-actions--mobile .btn-refresh {
    width: 100%;
    min-height: 40px;
    font-size: 13px;
  }

  .page-head {
    flex-direction: column;
    align-items: stretch;
  }

  .btn-refresh {
    width: 100%;
    min-height: 44px;
  }

  .workers-panel {
    padding: 12px;
  }

  .fe-page {
    gap: 8px;
  }
}
</style>

<!-- Teleport 모달: scoped 밖 전역 클래스 (fe-sheet·backdrop는 styles.css) -->
<style>
.fe-dialog .dialog-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
}

.fe-dialog .dialog-head h2 {
  margin: 0;
  font-size: 1.1rem;
  line-height: 1.35;
  flex: 1;
  min-width: 0;
}

.fe-dialog .dialog-close {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: #f1f5f9;
  color: #475569;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.fe-dialog .dialog-close:hover {
  background: #e2e8f0;
}

.fe-dialog.history-panel .history-list {
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}
</style>

