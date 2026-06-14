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

    <!-- 등급 통계 (승인 목록보다 위 — 원그래프 즉시 확인) -->
    <section v-if="gradeStats" class="panel grade-stats-panel">
      <h2 class="section-heading">등급 통계</h2>
      <p class="panel-sub">
        <template v-if="gradeStats.grade_stats_mode === 'demo'">
          전원 평가완료(가상) · S 70% / A 15% / B 10% / C 5%
          <span class="demo-grade-badge">데모</span>
        </template>
        <template v-else>
          ERP 월별집계 인원 기준 · 평가 완료 인원만 등급 비율 (S/A/B/C)
        </template>
        <span v-if="gradeStats.computed_at_label" class="muted"> · 갱신 {{ gradeStats.computed_at_label }}</span>
      </p>
      <p v-if="gradeStats.grade_stats_mode === 'demo' && gradeStats.grade_stats_mode_label" class="demo-grade-notice">
        {{ gradeStats.grade_stats_mode_label }} — 6/16 실평가 시작 시 실제 데이터로 전환됩니다.
      </p>
      <FeGradeStatsPanel
        :stats="overallGradeStats"
        title="전체 현장"
        :subtitle="gradeStatsOverallSubtitle"
      />
      <div v-if="teamGradeStats.length" class="team-stats-block">
        <h3 class="team-stats-heading">팀별 현황 <span class="muted">(현장명 [N.시공사] → 공사N팀 · 소장 1명 = 현장 1곳)</span></h3>
        <div class="team-stats-grid">
          <div v-for="team in teamGradeStats" :key="String(team.team_key)" class="team-stat-card panel inner-panel">
            <FeGradeStatsPanel
              :stats="teamStatsPayload(team)"
              :title="String(team.team_label || team.team_key)"
              :subtitle="teamGradeSubtitle(team)"
              compact
            />
          </div>
        </div>
      </div>
    </section>

    <!-- 검토·승인 (항상 표시) -->
    <section class="panel hq-review-panel">
      <div class="hq-review-head">
        <div>
          <h2 class="hq-review-title">검토·승인</h2>
          <p class="panel-sub">
            모든 현장의 평가 현황을 조회할 수 있습니다. 승인 순서:
            <strong>정상익 차장(담당 검토·코멘트) → 조동문 전무(실장 최종승인) → 대표이사</strong>
          </p>
        </div>
        <div class="hq-review-actions">
          <button class="stitch-btn-secondary" type="button" :disabled="loadingHqApprovals" @click="refreshReviewQueue">
            {{ loadingHqApprovals ? "조회 중…" : "새로고침" }}
          </button>
          <button
            v-if="canBulkOfficerApprove && hqOfficerPending.length"
            class="stitch-btn-primary"
            type="button"
            @click="openOfficerApproveAllModal"
          >
            담당 일괄 검토·승인 ({{ hqOfficerPending.length }}개)
          </button>
          <button
            v-if="canBulkDirectorApprove && hqDirectorPending.length"
            class="stitch-btn-primary"
            type="button"
            @click="openDirectorApproveAllModal"
          >
            실장 일괄 최종승인 ({{ hqDirectorPending.length }}개)
          </button>
          <button
            v-if="ceoPendingApprovals.length"
            class="stitch-btn-primary"
            type="button"
            @click="openCeoApproveAllModal"
          >
            대표이사 최종승인 서명 ({{ ceoPendingApprovals.length }}개 현장)
          </button>
        </div>
      </div>

      <div class="review-kpi-grid">
        <div class="review-kpi-card">
          <span class="review-kpi-label">검토·승인 대기</span>
          <strong class="review-kpi-value">{{ reviewQueue.total_hq_action_count }}</strong>
          <span class="review-kpi-hint">포상 승인 + 소장 제출 현장</span>
        </div>
        <div class="review-kpi-card">
          <span class="review-kpi-label">포상 승인 대기</span>
          <strong class="review-kpi-value">{{ reviewQueue.pending_reward_count }}</strong>
        </div>
        <div class="review-kpi-card">
          <span class="review-kpi-label">담당 검토 대기</span>
          <strong class="review-kpi-value">{{ reviewQueue.pending_hq_officer_site_count ?? hqOfficerPending.length }}</strong>
          <span class="review-kpi-hint">정상익 차장 · 소장 제출 완료</span>
        </div>
        <div class="review-kpi-card">
          <span class="review-kpi-label">실장 승인 대기</span>
          <strong class="review-kpi-value">{{ reviewQueue.pending_hq_director_site_count ?? hqDirectorPending.length }}</strong>
          <span class="review-kpi-hint">조동문 전무 · 담당 승인 후</span>
        </div>
        <div class="review-kpi-card review-kpi-card--warn">
          <span class="review-kpi-label">평가 완료·제출 전</span>
          <strong class="review-kpi-value">{{ reviewQueue.eval_complete_not_submitted_count }}</strong>
          <span class="review-kpi-hint">팀장 서명 또는 소장 제출 대기</span>
        </div>
        <div class="review-kpi-card review-kpi-card--muted">
          <span class="review-kpi-label">포상·제재 등록 현장</span>
          <strong class="review-kpi-value">{{ reviewQueue.sites_with_evidence_count }}</strong>
          <span class="review-kpi-hint">현장 등록 이력 (제출 전 포함)</span>
        </div>
      </div>

      <p v-if="consentSignedAt && !consentRequired" class="consent-done meta">
        동의서 서명 완료 · {{ consentSignedAt }}
        <button class="link-btn" type="button" @click="downloadConsentDoc">동의서 PDF</button>
      </p>

      <div v-if="siteSubmitBlockers.length" class="inner-section approval-collapse">
        <div class="approval-collapse__head">
          <button
            type="button"
            class="approval-collapse__toggle"
            :aria-expanded="approvalSectionsOpen.submitBlockers"
            @click="toggleApprovalSection('submitBlockers')"
          >
            <span class="approval-collapse__chevron" :class="{ 'is-open': approvalSectionsOpen.submitBlockers }">▸</span>
            <span class="approval-collapse__title">평가 완료 — 본사 서명 전 현장</span>
            <span class="approval-collapse__count">{{ siteSubmitBlockers.length }}곳</span>
          </button>
        </div>
        <div v-show="approvalSectionsOpen.submitBlockers" class="approval-collapse__body">
          <p class="panel-sub">
            「완료 현장」은 <strong>전원 평가 완료</strong>를 뜻합니다. 본사 검토·서명은 아래 순서가 끝난 뒤 가능합니다.
            <strong>팀장 보고서 서명 → 소장 최종 제출 → 본사 검토·서명</strong>
          </p>
          <div class="table-scroll">
            <table class="data-table">
              <thead>
                <tr>
                  <th>현장</th>
                  <th>평가</th>
                  <th>다음 단계</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in siteSubmitBlockers" :key="String(row.site_code)">
                  <td>{{ row.site_name || row.site_code }} <span class="muted">({{ row.site_code }})</span></td>
                  <td>{{ row.site_complete_workers }}/{{ row.site_total_workers }}</td>
                  <td class="blocker-label">{{ row.blocker_label }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <p
        v-if="reviewQueue.total_hq_action_count === 0 && !siteSubmitBlockers.length && reviewQueue.sites_with_evidence_count > 0"
        class="attendance-warn review-hint"
      >
        포상·제재 이력은 있으나, 소장이 「평가완료보고서 최종 제출」을 하기 전에는 현장 검토·서명 버튼이 활성화되지 않습니다.
        포상 사진은 아래 목록에서 승인할 수 있습니다.
      </p>

      <div v-if="pendingRewards.length" class="inner-section approval-collapse">
        <div class="approval-collapse__head">
          <button
            type="button"
            class="approval-collapse__toggle"
            :aria-expanded="approvalSectionsOpen.rewards"
            @click="toggleApprovalSection('rewards')"
          >
            <span class="approval-collapse__chevron" :class="{ 'is-open': approvalSectionsOpen.rewards }">▸</span>
            <span class="approval-collapse__title">고객사 포상 승인 대기</span>
            <span class="approval-collapse__count">{{ pendingRewards.length }}건</span>
          </button>
        </div>
        <div v-show="approvalSectionsOpen.rewards" class="approval-collapse__body">
          <div class="table-scroll">
            <table class="data-table">
              <thead>
                <tr>
                  <th>현장</th>
                  <th>근로자</th>
                  <th>가점</th>
                  <th>제출</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in pendingRewards" :key="row.id">
                  <td>{{ row.site_code }}</td>
                  <td>{{ row.worker_name }}</td>
                  <td>+{{ row.bonus_points }}</td>
                  <td>{{ formatDateTimeKst(row.created_at, "—") }}</td>
                  <td class="actions-inline">
                    <button class="link-btn" type="button" @click="previewRewardPhoto(row.id)">사진</button>
                    <button class="stitch-btn-primary" type="button" :disabled="rewardReviewing" @click="approveReward(row.id)">승인</button>
                    <button class="stitch-btn-secondary" type="button" :disabled="rewardReviewing" @click="rejectReward(row.id)">반려</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div v-if="hqOfficerPending.length" class="inner-section approval-collapse">
        <div class="approval-collapse__head">
          <button
            type="button"
            class="approval-collapse__toggle"
            :aria-expanded="approvalSectionsOpen.officer"
            @click="toggleApprovalSection('officer')"
          >
            <span class="approval-collapse__chevron" :class="{ 'is-open': approvalSectionsOpen.officer }">▸</span>
            <span class="approval-collapse__title">담당 검토 대기 (정상익 차장)</span>
            <span class="approval-collapse__count">{{ hqOfficerPending.length }}곳</span>
          </button>
          <div v-if="canBulkOfficerApprove" class="approval-collapse__actions">
            <button class="stitch-btn-primary" type="button" @click="openOfficerApproveAllModal">
              일괄 검토·승인
            </button>
          </div>
        </div>
        <div v-show="approvalSectionsOpen.officer" class="approval-collapse__body">
          <div class="table-scroll">
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
                <tr v-for="row in hqOfficerPending" :key="String(row.site_code)">
                  <td>
                    <button class="link-btn site-name-link" type="button" @click="openSiteByCode(String(row.site_code), row)">
                      {{ approvalSiteLabel(row) }}
                    </button>
                  </td>
                  <td>{{ row.site_complete_workers }}/{{ row.site_total_workers }}</td>
                  <td>{{ formatDateTimeKst(row.site_submitted_at_label || row.site_submitted_at, "—") }}</td>
                  <td class="actions-inline">
                    <button v-if="canOfficerApprove" class="stitch-btn-primary" type="button" @click="openSiteOfficerApprove(String(row.site_code))">검토·승인</button>
                    <button v-if="canOfficerApprove" class="stitch-btn-secondary" type="button" @click="rejectHq(String(row.site_code), 'officer')">반려</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div v-if="hqDirectorPending.length" class="inner-section approval-collapse">
        <div class="approval-collapse__head">
          <button
            type="button"
            class="approval-collapse__toggle"
            :aria-expanded="approvalSectionsOpen.director"
            @click="toggleApprovalSection('director')"
          >
            <span class="approval-collapse__chevron" :class="{ 'is-open': approvalSectionsOpen.director }">▸</span>
            <span class="approval-collapse__title">실장 최종승인 대기 (조동문 전무)</span>
            <span class="approval-collapse__count">{{ hqDirectorPending.length }}곳</span>
          </button>
          <div v-if="canBulkDirectorApprove" class="approval-collapse__actions">
            <button class="stitch-btn-primary" type="button" @click="openDirectorApproveAllModal">
              일괄 최종승인
            </button>
          </div>
        </div>
        <div v-show="approvalSectionsOpen.director" class="approval-collapse__body">
          <div class="table-scroll">
            <table class="data-table">
              <thead>
                <tr>
                  <th>현장</th>
                  <th>완료</th>
                  <th>담당승인</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in hqDirectorPending" :key="String(row.site_code)">
                  <td>
                    <button class="link-btn site-name-link" type="button" @click="openSiteByCode(String(row.site_code), row)">
                      {{ approvalSiteLabel(row) }}
                    </button>
                  </td>
                  <td>{{ row.site_complete_workers }}/{{ row.site_total_workers }}</td>
                  <td>{{ formatDateTimeKst(row.hq_officer_approved_at_label || row.hq_officer_approved_at, "—") }}</td>
                  <td class="actions-inline">
                    <button v-if="canDirectorApprove" class="stitch-btn-primary" type="button" @click="openSiteDirectorApprove(String(row.site_code))">최종승인</button>
                    <button v-if="canDirectorApprove" class="stitch-btn-secondary" type="button" @click="rejectHq(String(row.site_code), 'director')">반려</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div v-if="ceoPendingApprovals.length" class="inner-section approval-collapse">
        <div class="approval-collapse__head">
          <button
            type="button"
            class="approval-collapse__toggle"
            :aria-expanded="approvalSectionsOpen.ceo"
            @click="toggleApprovalSection('ceo')"
          >
            <span class="approval-collapse__chevron" :class="{ 'is-open': approvalSectionsOpen.ceo }">▸</span>
            <span class="approval-collapse__title">대표이사 최종 승인 대기</span>
            <span class="approval-collapse__count">{{ ceoPendingApprovals.length }}곳</span>
          </button>
          <div class="approval-collapse__actions">
            <button class="stitch-btn-primary" type="button" @click="openCeoApproveAllModal">
              일괄 최종승인
            </button>
          </div>
        </div>
        <div v-show="approvalSectionsOpen.ceo" class="approval-collapse__body">
          <div class="table-scroll">
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
                <tr v-for="row in ceoPendingApprovals" :key="`ceo-${String(row.site_code)}`">
                  <td>
                    <button class="link-btn site-name-link" type="button" @click="openSiteByCode(String(row.site_code), row)">
                      {{ approvalSiteLabel(row) }}
                    </button>
                  </td>
                  <td>{{ row.site_complete_workers }}/{{ row.site_total_workers }}</td>
                  <td>{{ formatDateTimeKst(row.hq_approved_at_label || row.hq_approved_at, "—") }}</td>
                  <td class="actions-inline">
                    <button class="stitch-btn-secondary" type="button" @click="rejectCeo(String(row.site_code))">반려</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>

    <!-- 대표·본사용 현황 대시보드 -->
    <section class="panel dashboard-panel">
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
          <span class="bucket-card__label">평가 완료 현장</span>
          <span class="bucket-card__count">{{ bucketCounts.completed }}</span>
          <span class="bucket-card__hint">전원 평가 완료 (본사 서명과 별개)</span>
        </button>
        <button
          type="button"
          class="bucket-card bucket-card--all"
          @click="selectBucket('all')"
        >
          <span class="bucket-card__label">전체 현장</span>
          <span class="bucket-card__count">{{ sites.length }}</span>
          <span class="bucket-card__hint">모든 현장 평가 현황 조회</span>
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

    <Teleport to="body">
      <div v-if="siteDetailModalOpen && selectedSite" class="fe-site-modal-overlay" @click.self="closeSite">
        <div class="fe-site-modal panel site-detail-panel" role="dialog" aria-modal="true">
          <div class="detail-head">
            <div class="detail-head-text">
              <h2>{{ selectedSite.site_name }}</h2>
              <p class="panel-sub">
                {{ selectedSite.site_code }} · 소장 {{ selectedSite.evaluator_name }}
                · 진행 <strong>{{ siteDetail?.site?.progress || selectedSite.progress }}</strong>
                <span v-if="siteApproval?.status_label"> · {{ siteApproval.status_label }}</span>
                <span v-if="siteApproval?.hq_officer_comment" class="muted"> · 담당: {{ siteApproval.hq_officer_comment }}</span>
              </p>
            </div>
            <div class="detail-head-actions">
              <button class="stitch-btn-secondary" type="button" :disabled="exportingEval" @click="downloadSiteEvalStatus(selectedSite.site_code)">
                {{ exportingEval ? "출력 중…" : "평가현황표" }}
              </button>
              <button class="stitch-btn-secondary" type="button" :disabled="exportingGrade" @click="downloadSiteGradeWorkbook(selectedSite.site_code)">
                {{ exportingGrade ? "출력 중…" : "등급표" }}
              </button>
              <button
                v-if="canOfficerApprove && siteApproval?.status === 'SITE_APPROVED'"
                class="stitch-btn-primary"
                type="button"
                @click="openSiteOfficerApprove(selectedSite.site_code)"
              >
                담당 검토·승인
              </button>
              <button
                v-if="canDirectorApprove && siteApproval?.status === 'HQ_OFFICER_APPROVED'"
                class="stitch-btn-primary"
                type="button"
                @click="openSiteDirectorApprove(selectedSite.site_code)"
              >
                실장 최종승인
              </button>
              <button class="stitch-btn-secondary" type="button" @click="closeSite">닫기</button>
            </div>
          </div>
          <div v-if="siteApproval" class="approval-summary">
            <span>평가 완료 {{ siteApproval.site_complete_workers }}/{{ siteApproval.site_total_workers }}명</span>
            <span v-if="siteApproval.team_total"> · 팀원 {{ siteApproval.team_complete }}/{{ siteApproval.team_total }}</span>
            <span v-if="siteApproval.direct_total"> · 직영 {{ siteApproval.direct_complete }}/{{ siteApproval.direct_total }}</span>
          </div>
          <FeGradeStatsPanel
            v-if="siteModalGradeStats"
            :stats="siteModalGradeStats"
            :title="`${selectedSite.site_name} 등급`"
            compact
          />
          <div v-if="loadingSite" class="muted">불러오는 중...</div>
          <div v-else class="table-scroll fe-site-modal-table">
            <table class="data-table roster-like-table">
              <thead>
                <tr>
                  <th>성명</th>
                  <th>상태</th>
                  <th>기능 (2-1)</th>
                  <th>안전·제재 (2-2)</th>
                  <th>비고</th>
                  <th class="col-actions">관리</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in evalRows" :key="row.worker_id" :class="row.needs_highlight ? 'row-highlight--alert' : ''">
                  <td>{{ row.name }}</td>
                  <td><span :class="evalStatusClass(row.eval_status)">{{ row.eval_status_label || "—" }}</span></td>
                  <td><span :class="gradeClass(row.functional_grade)">{{ row.functional_grade }}</span></td>
                  <td><span :class="gradeClass(row.safety_grade)">{{ row.safety_grade }}</span></td>
                  <td class="remark">{{ row.remark }}</td>
                  <td class="col-actions">
                    <HqEvalWorkerActions
                      :worker-id="row.worker_id"
                      :worker-name="row.name"
                      :period-closed="Boolean(period?.is_closed)"
                      :is-permanently-expelled="Boolean(row.is_permanently_expelled)"
                      @saved="reloadSiteDetail"
                    />
                  </td>
                </tr>
                <tr v-if="!evalRows.length">
                  <td colspan="6" class="muted">출역 대상 근로자가 없습니다.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Teleport>

    <section class="panel collapsible ops-panel">
      <button class="section-toggle" type="button" @click="showOps = !showOps">
        {{ showOps ? "▾" : "▸" }} 마감·운영
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

    <FeConsentGate v-if="consentRequired" :open="consentRequired" @completed="onConsentCompleted" />
    <FeSignatureModal
      ref="hqSignatureModalRef"
      :open="hqSignatureModalOpen"
      :title="hqSignatureModalTitle"
      :description="hqSignatureModalDescription"
      :review-mode="signatureReviewMode"
      submit-label="서명 및 승인"
      @update:open="(v) => (hqSignatureModalOpen = v)"
      @submit="onHqSignatureSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import HqEvalWorkerActions from "@/components/functional-eval/HqEvalWorkerActions.vue";
import FeConsentGate from "@/components/functional-eval/FeConsentGate.vue";
import FeSignatureModal from "@/components/functional-eval/FeSignatureModal.vue";
import FeGradeStatsPanel, { type GradeStatsPayload } from "@/components/functional-eval/FeGradeStatsPanel.vue";
import { api } from "@/services/api";
import { useAuthStore } from "@/stores/auth";
import { formatDateTimeKst, todayKst } from "@/utils/datetime";

const auth = useAuthStore();
const HQ_OFFICER_LOGIN = "안전보건-정상익";
const HQ_DIRECTOR_LOGIN = "안전보건-조동문";

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

type SiteBucket = "in_progress" | "not_started" | "completed" | "all";

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
  is_permanently_expelled?: boolean;
  sanction_count?: number;
}

interface SiteApprovalSummary {
  status?: string;
  status_label?: string;
  hq_officer_approved_at?: string | null;
  hq_officer_comment?: string | null;
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

interface PendingReward {
  id: number;
  worker_name: string;
  site_code: string;
  bonus_points: number;
  created_at?: string;
}

interface SiteSubmitBlocker {
  site_code: string;
  site_name?: string;
  blocker_label: string;
  blocker_stage?: string;
  site_complete_workers?: number;
  site_total_workers?: number;
}

const period = ref<Period | null>(null);
const totals = ref<Totals | null>(null);
const sites = ref<SiteRow[]>([]);
const selectedSite = ref<SiteRow | null>(null);
const siteDetailModalOpen = ref(false);
const siteDetail = ref<{ site: SiteRow; approval?: SiteApprovalSummary } | null>(null);
const siteApproval = computed(() => siteDetail.value?.approval ?? null);
const evalRows = ref<EvalRow[]>([]);
const loadingSite = ref(false);
const exporting = ref(false);
const exportingEval = ref(false);
const exportingGrade = ref(false);
const deadlineInput = ref("");
const sortBy = ref("progress");
const sortDir = ref("desc");
const siteSearch = ref("");
const loadError = ref("");
const showAdmin = ref(false);
const showOps = ref(false);
const pendingRewards = ref<PendingReward[]>([]);
const loadingPendingRewards = ref(false);
const rewardReviewing = ref(false);
const reviewQueue = ref({
  pending_reward_count: 0,
  pending_hq_site_count: 0,
  pending_hq_officer_site_count: 0,
  pending_hq_director_site_count: 0,
  pending_ceo_site_count: 0,
  total_hq_action_count: 0,
  sites_with_evidence_count: 0,
  eval_complete_not_submitted_count: 0,
  site_submit_blockers: [] as SiteSubmitBlocker[],
});

const siteSubmitBlockers = computed(() => reviewQueue.value.site_submit_blockers ?? []);
const consentSignedAt = ref("");
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
const gradeStats = ref<{
  overall?: GradeStatsPayload;
  by_team?: Record<string, unknown>[];
  erp_headcount_total?: number;
  computed_at_label?: string;
  grade_stats_mode?: string;
  grade_stats_mode_label?: string;
  grade_stats_live_from?: string;
} | null>(null);
const siteModalGradeStats = ref<GradeStatsPayload | null>(null);

const overallGradeStats = computed(() => gradeStats.value?.overall ?? null);
const teamGradeStats = computed(() => gradeStats.value?.by_team ?? []);

const gradeStatsOverallSubtitle = computed(() => {
  const fn = gradeStats.value?.overall?.functional;
  const erpTotal = Number(gradeStats.value?.erp_headcount_total ?? fn?.workers_total ?? 0);
  const attendance = fn?.attendance_workers;
  const demo = gradeStats.value?.grade_stats_mode === "demo";
  if (demo) {
    return `근로자 ${erpTotal}명 · 전원 평가완료(가상)`;
  }
  if (attendance != null && attendance !== erpTotal) {
    return `ERP ${erpTotal}명 · 출역 ${attendance}명`;
  }
  return `근로자 ${erpTotal}명`;
});

function teamStatsPayload(team: Record<string, unknown>): GradeStatsPayload {
  return {
    functional: team.functional as GradeStatsPayload["functional"],
    safety: team.safety as GradeStatsPayload["safety"],
  };
}

function teamGradeSubtitle(team: Record<string, unknown>) {
  const sites = Number(team.site_count ?? 0);
  const workers = Number((team.functional as { workers_total?: number } | undefined)?.workers_total ?? 0);
  const labels = team.contractor_labels as string[] | undefined;
  const single = String(team.contractor_label || "").trim();
  let suffix = "";
  if (labels && labels.length > 1) {
    suffix = ` · ${labels.length}개 시공사`;
  } else if (single) {
    suffix = ` · ${single}`;
  }
  return `${sites}개 현장 · ${workers}명${suffix}`;
}

function siteStatsPayload(data: Record<string, unknown>): GradeStatsPayload {
  return {
    functional: data.functional as GradeStatsPayload["functional"],
    safety: data.safety as GradeStatsPayload["safety"],
  };
}

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
  if (activeBucket.value === "completed") return "평가 완료 현장";
  if (activeBucket.value === "all") return "전체 현장";
  return "";
});

const bucketSites = computed(() => {
  if (!activeBucket.value) return [];
  if (activeBucket.value === "all") return sites.value;
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
const hqRole = ref("staff");
const hqOfficerPending = ref<Record<string, unknown>[]>([]);
const hqDirectorPending = ref<Record<string, unknown>[]>([]);

type ApprovalSectionKey = "submitBlockers" | "rewards" | "officer" | "director" | "ceo";
const approvalSectionsOpen = ref<Record<ApprovalSectionKey, boolean>>({
  submitBlockers: false,
  rewards: false,
  officer: false,
  director: false,
  ceo: false,
});

function toggleApprovalSection(key: ApprovalSectionKey) {
  approvalSectionsOpen.value[key] = !approvalSectionsOpen.value[key];
}
const hqPendingApprovals = ref<Record<string, unknown>[]>([]);
const ceoPendingApprovals = ref<Record<string, unknown>[]>([]);
const consentRequired = ref(false);
const hqSignatureModalOpen = ref(false);
const hqSignatureModalRef = ref<InstanceType<typeof FeSignatureModal> | null>(null);
const hqSignatureMode = ref<"officer-all" | "director-all" | "officer-site" | "director-site" | "ceo">("officer-all");
const pendingApproveSiteCode = ref("");

const loginId = computed(() => (auth.user?.login_id || "").trim());
const canOfficerApprove = computed(
  () => loginId.value === HQ_OFFICER_LOGIN || hqRole.value === "admin",
);
const canDirectorApprove = computed(
  () => loginId.value === HQ_DIRECTOR_LOGIN || hqRole.value === "admin",
);
const canBulkOfficerApprove = computed(() => canOfficerApprove.value);
const canBulkDirectorApprove = computed(() => canDirectorApprove.value);

const signatureReviewMode = computed(() => {
  if (hqSignatureMode.value === "officer-all" || hqSignatureMode.value === "officer-site") return "officer";
  if (hqSignatureMode.value === "director-all" || hqSignatureMode.value === "director-site") return "director";
  return "none";
});

const hqSignatureModalTitle = computed(() => {
  if (hqSignatureMode.value === "ceo") return "대표이사 전체 최종승인 서명";
  if (hqSignatureMode.value.startsWith("officer")) return "안전보건 담당 검토·승인";
  return "안전보건실장 최종승인";
});
const hqSignatureModalDescription = computed(() => {
  if (hqSignatureMode.value === "ceo") {
    return `대기 ${ceoPendingApprovals.value.length}개 현장을 일괄 최종승인합니다.`;
  }
  if (hqSignatureMode.value === "officer-all") {
    return `검토 코멘트 입력 후 서명합니다. (대기 ${hqOfficerPending.value.length}개 현장)`;
  }
  if (hqSignatureMode.value === "director-all") {
    return `담당 승인 완료 현장 ${hqDirectorPending.value.length}곳을 일괄 최종승인합니다.`;
  }
  if (hqSignatureMode.value === "officer-site") {
    return `현장 ${pendingApproveSiteCode.value} — 담당 검토·승인`;
  }
  return `현장 ${pendingApproveSiteCode.value} — 실장 최종승인`;
});

async function checkConsent() {
  try {
    const res = await api.get("/functional-eval/consent/status");
    consentRequired.value = Boolean(res.data.required);
    consentSignedAt.value = res.data.signed_at_label || res.data.signed_at || "";
  } catch {
    consentRequired.value = false;
    consentSignedAt.value = "";
  }
}

async function downloadConsentDoc() {
  try {
    const res = await api.get("/functional-eval/consent/document", { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch {
    window.alert("동의서 PDF를 불러오지 못했습니다.");
  }
}

async function refreshReviewQueue() {
  loadingHqApprovals.value = true;
  loadingPendingRewards.value = true;
  try {
    await Promise.all([loadHqApprovals(), loadPendingRewards(), loadOverview()]);
  } finally {
    loadingPendingRewards.value = false;
  }
}

function openOfficerApproveAllModal() {
  hqSignatureMode.value = "officer-all";
  pendingApproveSiteCode.value = "";
  hqSignatureModalOpen.value = true;
}

function openDirectorApproveAllModal() {
  hqSignatureMode.value = "director-all";
  pendingApproveSiteCode.value = "";
  hqSignatureModalOpen.value = true;
}

function openSiteOfficerApprove(siteCode: string) {
  hqSignatureMode.value = "officer-site";
  pendingApproveSiteCode.value = siteCode;
  hqSignatureModalOpen.value = true;
}

function openSiteDirectorApprove(siteCode: string) {
  hqSignatureMode.value = "director-site";
  pendingApproveSiteCode.value = siteCode;
  hqSignatureModalOpen.value = true;
}

function openCeoApproveAllModal() {
  hqSignatureMode.value = "ceo";
  pendingApproveSiteCode.value = "";
  hqSignatureModalOpen.value = true;
}

async function onHqSignatureSubmit(payload: {
  signature_data: string;
  consent_acknowledged: boolean;
  officer_comment?: string;
  director_comment?: string;
}) {
  hqSignatureModalRef.value?.setSubmitting(true);
  try {
    let path = "/functional-eval/hq/ceo-approvals/approve-all";
    if (hqSignatureMode.value === "officer-all") {
      path = "/functional-eval/hq/approvals/officer/approve-all";
    } else if (hqSignatureMode.value === "director-all") {
      path = "/functional-eval/hq/approvals/director/approve-all";
    } else if (hqSignatureMode.value === "officer-site") {
      path = `/functional-eval/hq/approvals/officer/${encodeURIComponent(pendingApproveSiteCode.value)}/approve`;
    } else if (hqSignatureMode.value === "director-site") {
      path = `/functional-eval/hq/approvals/director/${encodeURIComponent(pendingApproveSiteCode.value)}/approve`;
    }
    await api.post(path, payload);
    hqSignatureModalOpen.value = false;
    await refreshReviewQueue();
    if (selectedSite.value) await reloadSiteDetail();
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    hqSignatureModalRef.value?.setError(typeof msg === "string" ? msg : "승인 서명에 실패했습니다.");
  } finally {
    hqSignatureModalRef.value?.setSubmitting(false);
  }
}

async function loadHqApprovals() {
  loadingHqApprovals.value = true;
  try {
    const [hqRes, ceoRes] = await Promise.allSettled([
      api.get("/functional-eval/hq/approvals/pending"),
      api.get("/functional-eval/hq/ceo-approvals/pending"),
    ]);
    if (hqRes.status === "fulfilled") {
      hqRole.value = hqRes.value.data.hq_role || "staff";
      hqOfficerPending.value = hqRes.value.data.officer_items || [];
      hqDirectorPending.value = hqRes.value.data.director_items || [];
      hqPendingApprovals.value = hqRes.value.data.items || [];
    } else {
      hqOfficerPending.value = [];
      hqDirectorPending.value = [];
      hqPendingApprovals.value = [];
    }
    ceoPendingApprovals.value =
      ceoRes.status === "fulfilled" ? ceoRes.value.data.items || [] : [];
    syncReviewQueueCounts();
  } finally {
    loadingHqApprovals.value = false;
  }
}

async function rejectHq(siteCode: string, stage: "officer" | "director" = "officer") {
  const note = window.prompt("반려 사유 (선택)") || "";
  const path =
    stage === "director"
      ? `/functional-eval/hq/approvals/director/${encodeURIComponent(siteCode)}/reject`
      : `/functional-eval/hq/approvals/${encodeURIComponent(siteCode)}/reject`;
  await api.post(path, { note });
  await loadHqApprovals();
  if (selectedSite.value?.site_code === siteCode) await reloadSiteDetail();
}

function openSiteByCode(siteCode: string, row?: Record<string, unknown>) {
  const site = sites.value.find((s) => s.site_code === siteCode);
  if (site) {
    void openSite(site);
    return;
  }
  const name = row ? approvalSiteLabel(row) : siteCode;
  void openSite({
    site_code: siteCode,
    site_name: name,
    evaluator_name: "—",
    total: Number(row?.site_total_workers) || 0,
    fully_complete: Number(row?.site_complete_workers) || 0,
    progress: row?.site_total_workers
      ? `${row.site_complete_workers}/${row.site_total_workers}`
      : "—",
    has_completed: false,
  });
}

async function downloadSiteEvalStatus(siteCode: string) {
  exportingEval.value = true;
  try {
    const res = await api.get("/functional-eval/hq/export/evaluations", {
      params: { site_code: siteCode },
      responseType: "blob",
    });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `평가현황_${siteCode}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    window.alert("평가현황표를 다운로드하지 못했습니다.");
  } finally {
    exportingEval.value = false;
  }
}

async function approveCeo(_siteCode: string) {
  openCeoApproveAllModal();
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
  a.download = `기능인제_평가자계정_${todayKst()}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

async function loadGradeStats() {
  try {
    const res = await api.get("/functional-eval/hq/grade-stats");
    gradeStats.value = res.data;
  } catch {
    gradeStats.value = null;
  }
}

async function loadSiteGradeStats(siteCode: string) {
  try {
    const res = await api.get(`/functional-eval/hq/sites/${encodeURIComponent(siteCode)}/grade-stats`);
    siteModalGradeStats.value = siteStatsPayload(res.data);
  } catch {
    siteModalGradeStats.value = null;
  }
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
    if (res.data.review_queue) {
      reviewQueue.value = { ...reviewQueue.value, ...res.data.review_queue };
    }
    if (!sites.value.length && (totals.value?.workers ?? 0) > 0) {
      loadError.value = "현장 목록을 불러오지 못했습니다. 새로고침(Ctrl+F5) 후 다시 시도해 주세요.";
    }
    deadlineInput.value = period.value?.deadline_date || "";
    await loadGradeStats();
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

function approvalSiteLabel(row: Record<string, unknown>) {
  const code = String(row.site_code || "");
  const fromRow = String(row.site_name || "").trim();
  if (fromRow && fromRow !== code) return fromRow;
  const fromList = sites.value.find((s) => s.site_code === code)?.site_name;
  return fromList || fromRow || code;
}


async function openSite(site: SiteRow) {
  selectedSite.value = site;
  siteDetailModalOpen.value = true;
  if (!activeBucket.value && site.bucket) {
    activeBucket.value = site.bucket;
  }
  loadingSite.value = true;
  evalRows.value = [];
  siteModalGradeStats.value = null;
  try {
    const [evalRes] = await Promise.allSettled([
      api.get(`/functional-eval/hq/sites/${encodeURIComponent(site.site_code)}/evaluations`, {
        params: { sort_by: "name", sort_dir: "asc" },
      }),
      loadSiteGradeStats(site.site_code),
    ]);
    if (evalRes.status === "fulfilled") {
      siteDetail.value = evalRes.value.data;
      evalRows.value = evalRes.value.data.eval_rows || [];
      if (evalRes.value.data.site?.site_name) {
        selectedSite.value = { ...site, site_name: evalRes.value.data.site.site_name };
      }
    }
  } finally {
    loadingSite.value = false;
  }
}

function closeSite() {
  siteDetailModalOpen.value = false;
  selectedSite.value = null;
  siteDetail.value = null;
  evalRows.value = [];
  siteModalGradeStats.value = null;
}

async function reloadSiteDetail() {
  if (!selectedSite.value) return;
  await openSite(selectedSite.value);
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
  return `현장별 기능인등급-${todayKst().replace(/-/g, "")}.xlsx`;
}


async function loadPendingRewards() {
  loadingPendingRewards.value = true;
  try {
    const res = await api.get("/functional-eval/hq/customer-rewards/pending");
    pendingRewards.value = res.data.items || [];
    syncReviewQueueCounts();
  } catch {
    pendingRewards.value = [];
    syncReviewQueueCounts();
  } finally {
    loadingPendingRewards.value = false;
  }
}

function syncReviewQueueCounts() {
  reviewQueue.value = {
    ...reviewQueue.value,
    pending_reward_count: pendingRewards.value.length,
    pending_hq_officer_site_count: hqOfficerPending.value.length,
    pending_hq_director_site_count: hqDirectorPending.value.length,
    pending_hq_site_count: hqOfficerPending.value.length + hqDirectorPending.value.length,
    pending_ceo_site_count: ceoPendingApprovals.value.length,
    total_hq_action_count:
      pendingRewards.value.length + hqOfficerPending.value.length + hqDirectorPending.value.length,
  };
}

async function previewRewardPhoto(rewardId: number) {
  try {
    const res = await api.get(`/functional-eval/customer-rewards/${rewardId}/photo`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch {
    window.alert("사진을 불러올 수 없습니다.");
  }
}

async function approveReward(rewardId: number) {
  rewardReviewing.value = true;
  try {
    await api.post(`/functional-eval/hq/customer-rewards/${rewardId}/approve`, {});
    await loadPendingRewards();
    if (selectedSite.value) await reloadSiteDetail();
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    window.alert(typeof detail === "string" ? detail : "승인에 실패했습니다.");
  } finally {
    rewardReviewing.value = false;
  }
}

async function rejectReward(rewardId: number) {
  const rejectNote = window.prompt("반려 사유 (선택)") || "";
  rewardReviewing.value = true;
  try {
    await api.post(`/functional-eval/hq/customer-rewards/${rewardId}/reject`, { reject_note: rejectNote });
    await loadPendingRewards();
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    window.alert(typeof detail === "string" ? detail : "반려에 실패했습니다.");
  } finally {
    rewardReviewing.value = false;
  }
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

async function onConsentCompleted() {
  consentRequired.value = false;
  await checkConsent();
}

onMounted(async () => {
  await checkConsent();
  await loadOverview();
  await loadHqApprovals();
  await loadPendingRewards();
});
</script>

<style scoped>
.hq-review-panel { border-left: 4px solid #2563eb; }
.hq-review-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.hq-review-title { margin: 0 0 4px; font-size: 18px; }
.hq-review-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.review-kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 12px; }
.review-kpi-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 4px; }
.review-kpi-card--muted { background: #fff; }
.review-kpi-card--warn { border-left: 3px solid #ea580c; }
.blocker-label { color: #c2410c; font-weight: 600; }
.submit-blockers .panel-sub { margin: 0 0 10px; font-size: 13px; color: #475569; }
.review-kpi-label { font-size: 12px; color: #64748b; }
.review-kpi-value { font-size: 24px; line-height: 1.1; color: #0f172a; }
.review-kpi-hint { font-size: 11px; color: #94a3b8; }
.consent-done { margin: 0 0 8px; }
.review-hint { margin: 0 0 8px; }
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
.col-actions { width: 220px; white-space: nowrap; }
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
.detail-head-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.team-stats-heading { margin: 20px 0 12px; font-size: 15px; font-weight: 600; }
.team-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}
.team-stat-card { padding: 12px; margin: 0; }
.grade-stats-panel { margin-bottom: 16px; padding: 20px; }
.demo-grade-notice {
  margin: 0 0 12px;
  padding: 10px 12px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  font-size: 13px;
  color: #92400e;
}
.demo-grade-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 600;
  color: #92400e;
  background: #fef3c7;
  border-radius: 4px;
}
.grade-stats-section { margin-bottom: 20px; padding-bottom: 16px; border-bottom: 1px solid #e2e8f0; }
.section-heading { margin: 0 0 4px; font-size: 18px; }
.inner-panel { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; }
.bucket-card--all { border-top: 4px solid #6366f1; }
.site-name-link { text-align: left; max-width: 420px; white-space: normal; line-height: 1.35; }
.approval-collapse { padding: 0; overflow: hidden; }
.approval-collapse__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}
.approval-collapse__toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: inherit;
}
.approval-collapse__toggle:hover .approval-collapse__title { color: #2563eb; }
.approval-collapse__chevron {
  display: inline-block;
  width: 16px;
  flex-shrink: 0;
  font-size: 14px;
  color: #64748b;
  transition: transform 0.15s ease;
}
.approval-collapse__chevron.is-open { transform: rotate(90deg); }
.approval-collapse__title {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}
.approval-collapse__count {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: #2563eb;
  background: #eff6ff;
  padding: 2px 8px;
  border-radius: 999px;
}
.approval-collapse__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.approval-collapse__body {
  padding: 12px 4px 4px;
}
</style>

<style>
.fe-site-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 550;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 24px 16px;
  overflow-y: auto;
}
.fe-site-modal {
  width: min(1100px, 100%);
  max-height: calc(100vh - 48px);
  overflow: auto;
  margin: 0 auto;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.18);
}
.fe-site-modal-table { max-height: min(60vh, 520px); }
.fe-site-modal .detail-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.fe-site-modal .detail-head-text { flex: 1; min-width: 200px; }
.fe-site-modal .detail-head-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.fe-site-modal .approval-summary {
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
