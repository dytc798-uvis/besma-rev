import { createRouter, createWebHistory, RouteRecordRaw } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import LoginPage from "@/pages/LoginPage.vue";
import HQSafeLayout from "@/layouts/HQSafeLayout.vue";
import SiteLayout from "@/layouts/SiteLayout.vue";
import HQOtherLayout from "@/layouts/HQOtherLayout.vue";
import HQSafeDashboard from "@/pages/dashboard/HQSafeDashboard.vue";
import HQSafeHomePage from "@/pages/dashboard/HQSafeHomePage.vue";
import SiteDashboard from "@/pages/dashboard/SiteDashboard.vue";
import HQOtherDashboard from "@/pages/dashboard/HQOtherDashboard.vue";
import DocumentListPage from "@/pages/documents/DocumentListPage.vue";
import DocumentDetailPage from "@/pages/documents/DocumentDetailPage.vue";
import DocumentUploadPage from "@/pages/documents/DocumentUploadPage.vue";
import RedirectLegacyTbmViewPage from "@/pages/documents/RedirectLegacyTbmViewPage.vue";
import ApprovalInboxPage from "@/pages/documents/ApprovalInboxPage.vue";
import ApprovalHistoryPage from "@/pages/documents/ApprovalHistoryPage.vue";
import OpinionListPage from "@/pages/opinions/OpinionListPage.vue";
import OpinionDetailPage from "@/pages/opinions/OpinionDetailPage.vue";
import PersonaSelectPage from "@/pages/PersonaSelectPage.vue";
import TestHQAdminPage from "@/pages/test/TestHQAdminPage.vue";
import TestSiteManagerPage from "@/pages/test/TestSiteManagerPage.vue";
import TestWorkerPage from "@/pages/test/TestWorkerPage.vue";
import WorkerMobileListPage from "@/pages/worker/WorkerMobileListPage.vue";
import WorkerMobileDetailPage from "@/pages/worker/WorkerMobileDetailPage.vue";
import SiteDailySafetyShellLayout from "@/layouts/SiteDailySafetyShellLayout.vue";
import SiteMobileOpsPage from "@/pages/site/SiteMobileOpsPage.vue";
import SiteMobileDailyCapturePage from "@/pages/site/SiteMobileDailyCapturePage.vue";
import HQWorkerSafetyRecordPage from "@/pages/hq/HQWorkerSafetyRecordPage.vue";
import HQCommunicationsPage from "@/pages/hq/HQCommunicationsPage.vue";
import HQDocumentsDashboardPage from "@/pages/hq/HQDocumentsDashboardPage.vue";
import HQDocumentInstanceDetailPage from "@/pages/hq/HQDocumentInstanceDetailPage.vue";
import HQDocumentExplorerPage from "@/pages/hq/HQDocumentExplorerPage.vue";
import HQPendingDocumentsPage from "@/pages/hq/HQPendingDocumentsPage.vue";
import HQSitesPage from "@/pages/hq/HQSitesPage.vue";
import HQUsersPage from "@/pages/hq/HQUsersPage.vue";
import HQDocumentSettingsPage from "@/pages/hq/HQDocumentSettingsPage.vue";
import HQContractorDocumentBundleSettingsPage from "@/pages/hq/HQContractorDocumentBundleSettingsPage.vue";
import HQPeriodicDocumentMonitoringPage from "@/pages/hq/HQPeriodicDocumentMonitoringPage.vue";
import HQAccidentsListPage from "@/pages/hq/HQAccidentsListPage.vue";
import HQAccidentInitialRegisterPage from "@/pages/hq/HQAccidentInitialRegisterPage.vue";
import HQAccidentDetailPage from "@/pages/hq/HQAccidentDetailPage.vue";
import HQAccidentWorklistPage from "@/pages/hq/HQAccidentWorklistPage.vue";
import HQAccidentReportPage from "@/pages/hq/HQAccidentReportPage.vue";
import RiskLibraryPage from "@/pages/risk/RiskLibraryPage.vue";
import SiteDocumentsDashboardPage from "@/pages/site/SiteDocumentsDashboardPage.vue";
import SiteNoticeBoardPage from "@/pages/site/SiteNoticeBoardPage.vue";
import SafetyPolicyGoalsPage from "@/pages/site/SafetyPolicyGoalsPage.vue";
import SafetyEducationInspectionCalendarPage from "@/pages/site/SafetyEducationInspectionCalendarPage.vue";
import NonconformityPage from "@/pages/site/NonconformityPage.vue";
import WorkerVoiceBoardPage from "@/pages/site/WorkerVoiceBoardPage.vue";
import DynamicMenuRuntimePage from "@/pages/site/DynamicMenuRuntimePage.vue";
import SiteCommunicationsPage from "@/pages/site/SiteCommunicationsPage.vue";
import SiteMobileCommunicationsPage from "@/pages/site/SiteMobileCommunicationsPage.vue";
import SiteMobileSiteSearchPage from "@/pages/site/SiteMobileSiteSearchPage.vue";
import SiteInfoPage from "@/pages/site/SiteInfoPage.vue";
import WorkPlanForkliftPage from "@/pages/site/WorkPlanForkliftPage.vue";
import CoupangMvpPage from "@/pages/site/CoupangMvpPage.vue";
import ChangePasswordPage from "@/pages/auth/ChangePasswordPage.vue";
import FeOnboardingPage from "@/pages/auth/FeOnboardingPage.vue";
import UserGuidePage from "@/pages/common/UserGuidePage.vue";
import FunctionalEvalLayout from "@/layouts/FunctionalEvalLayout.vue";
import SiteFunctionalEvalPage from "@/pages/functional-eval/SiteFunctionalEvalPage.vue";
import TbmBetaPage from "@/pages/functional-eval/TbmBetaPage.vue";
import SiteNewSiteDeploymentPage from "@/pages/site/SiteNewSiteDeploymentPage.vue";
import HQFunctionalEvalPage from "@/pages/hq/HQFunctionalEvalPage.vue";
import HQFunctionalEvalMonitoringPage from "@/pages/hq/HQFunctionalEvalMonitoringPage.vue";
import HQFunctionalEvalRewardsSanctionsPage from "@/pages/hq/HQFunctionalEvalRewardsSanctionsPage.vue";
import HQFunctionalEvalGradeReportPage from "@/pages/hq/HQFunctionalEvalGradeReportPage.vue";
import HQNewSiteDeploymentPage from "@/pages/hq/HQNewSiteDeploymentPage.vue";
import HQSystemBackupPage from "@/pages/hq/HQSystemBackupPage.vue";
import FieldFormUploadPage from "@/pages/field-form-uploads/FieldFormUploadPage.vue";
import SafetyLedgersPage from "@/pages/safety-ledgers/SafetyLedgersPage.vue";
import PdfSigningAdminPage from "@/pages/pdf-signing/PdfSigningAdminPage.vue";
import PdfSigningPublicPage from "@/pages/pdf-signing/PdfSigningPublicPage.vue";
import { isMobileOpsSiteLogin, siteMobileOrDesktopHomeName } from "@/utils/siteHomeRoute";
import { hqSafeHomeRouteName } from "@/utils/hqHomeRoute";
import { isPublicSignPath, normalizePublicSignPath } from "@/utils/publicSignRoute";

const HQ_SAFE_WORKSPACE_ROLES = new Set([
  "HQ_SAFE",
  "HQ_SAFE_ADMIN",
  "SUPER_ADMIN",
  "ACCIDENT_ADMIN",
]);
const WELERAZER_REFERENCE_LOGIN_ID = "어드민";

function canAccessHqSafeWorkspace(role: string | undefined) {
  return HQ_SAFE_WORKSPACE_ROLES.has(role ?? "") || role === "FUNCTIONAL_EVAL_VIEWER";
}

function isFunctionalEvalViewer(role: string | undefined) {
  return role === "FUNCTIONAL_EVAL_VIEWER";
}

function isWeleraserReference(loginId: string | undefined): boolean {
  return (loginId || "").trim() === WELERAZER_REFERENCE_LOGIN_ID;
}

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    redirect: { name: "login" },
  },
  {
    path: "/login",
    name: "login",
    component: LoginPage,
  },
  {
    path: "/sign/:token",
    name: "pdf-signing-public",
    component: PdfSigningPublicPage,
    meta: { publicSign: true },
  },
  {
    path: "/temp/sign1",
    name: "pdf-signing-temp-sign1",
    component: PdfSigningPublicPage,
    props: { fixedSlot: "sign1" },
    meta: { publicSign: true },
  },
  {
    path: "/temp/sign2",
    name: "pdf-signing-temp-sign2",
    component: PdfSigningPublicPage,
    props: { fixedSlot: "sign2" },
    meta: { publicSign: true },
  },
  {
    path: "/change-password",
    name: "change-password",
    component: ChangePasswordPage,
    meta: { requiresAuth: true },
  },
  {
    path: "/fe-onboarding",
    name: "fe-onboarding",
    component: FeOnboardingPage,
    meta: { requiresAuth: true },
  },
  {
    path: "/persona-select",
    name: "persona-select",
    component: PersonaSelectPage,
    meta: { requiresAuth: true, devOnly: true },
  },
  {
    path: "/hq-safe",
    component: HQSafeLayout,
    meta: { requiresAuth: true, uiType: "HQ_SAFE" },
    children: [
      { path: "", redirect: { name: "hq-safe-dashboard" } },
      { path: "dashboard", name: "hq-safe-dashboard", component: HQSafeHomePage },
      { path: "operations-dashboard", name: "hq-safe-operations-dashboard", component: HQSafeDashboard },
      { path: "field-form-uploads", name: "hq-safe-field-form-uploads", component: FieldFormUploadPage },
      { path: "safety-ledgers", redirect: { name: "hq-safe-card-expenses" } },
      { path: "card-expenses", name: "hq-safe-card-expenses", component: SafetyLedgersPage, meta: { ledgerTab: "card" } },
      { path: "vehicle-logs", name: "hq-safe-vehicle-logs", component: SafetyLedgersPage, meta: { ledgerTab: "vehicle" } },
      { path: "documents", name: "hq-safe-documents", component: HQDocumentsDashboardPage },
      {
        path: "document-instances/:instanceId",
        name: "hq-safe-document-instance-detail",
        component: HQDocumentInstanceDetailPage,
      },
      { path: "document-explorer", name: "hq-safe-document-explorer", component: HQDocumentExplorerPage },
      { path: "notices", name: "hq-safe-notices", component: SiteNoticeBoardPage },
      { path: "safety-policy-goals", name: "hq-safe-safety-policy-goals", component: SafetyPolicyGoalsPage },
      {
        path: "safety-education",
        name: "hq-safe-safety-education",
        component: SafetyEducationInspectionCalendarPage,
      },
      { path: "safety-inspections", redirect: { name: "hq-safe-safety-education" } },
      { path: "nonconformities", name: "hq-safe-nonconformities", component: NonconformityPage },
      {
        path: "accidents",
        name: "hq-safe-accidents",
        component: HQAccidentsListPage,
        meta: { requiresAccidentAdmin: true },
      },
      {
        path: "accidents/worklist",
        name: "hq-safe-accidents-worklist",
        component: HQAccidentWorklistPage,
        meta: { requiresAccidentAdmin: true },
      },
      {
        path: "accidents/new",
        name: "hq-safe-accidents-new",
        component: HQAccidentInitialRegisterPage,
        meta: { requiresAccidentAdmin: true },
      },
      {
        path: "accidents/:id",
        name: "hq-safe-accident-detail",
        component: HQAccidentDetailPage,
        meta: { requiresAccidentAdmin: true },
      },
      {
        path: "accidents/:id/report",
        name: "hq-safe-accident-report",
        component: HQAccidentReportPage,
        meta: { requiresAccidentAdmin: true },
      },
      {
        path: "pdf-signing",
        name: "hq-safe-pdf-signing",
        component: PdfSigningAdminPage,
        meta: { requiresPdfSigning: true },
      },
      { path: "worker-voice", name: "hq-safe-worker-voice", component: WorkerVoiceBoardPage },
      { path: "custom-menus/:slug", name: "hq-safe-dynamic-menu", component: DynamicMenuRuntimePage },
      { path: "documents/pending-review", name: "hq-safe-documents-pending", component: HQPendingDocumentsPage },
      { path: "documents/:id", name: "hq-safe-document-detail", component: DocumentDetailPage },
      { path: "documents/:id/tbm-view", name: "hq-safe-document-tbm-view", component: RedirectLegacyTbmViewPage },
      { path: "communications", name: "hq-safe-communications", component: HQCommunicationsPage },
      { path: "periodic-monitoring", name: "hq-safe-periodic-monitoring", component: HQPeriodicDocumentMonitoringPage },
      { path: "approvals/inbox", name: "hq-safe-approval-inbox", component: ApprovalInboxPage },
      {
        path: "approvals/history",
        name: "hq-safe-approval-history",
        component: ApprovalHistoryPage,
      },
      {
        path: "workers/:personId/safety-record",
        name: "hq-safe-worker-safety-record",
        component: HQWorkerSafetyRecordPage,
      },
      { path: "risk-library", name: "hq-safe-risk-library", component: RiskLibraryPage },
      { path: "site-search", name: "hq-safe-site-search", component: SiteMobileSiteSearchPage },
      { path: "opinions", name: "hq-safe-opinions", component: OpinionListPage },
      { path: "opinions/:id", name: "hq-safe-opinion-detail", component: OpinionDetailPage },
      { path: "sites", name: "hq-safe-sites", component: HQSitesPage },
      { path: "users", name: "hq-safe-users", component: HQUsersPage },
      { path: "settings", name: "hq-safe-settings", component: HQDocumentSettingsPage },
      {
        path: "contractor-document-settings",
        name: "hq-safe-contractor-document-settings",
        component: HQContractorDocumentBundleSettingsPage,
      },
      { path: "user-guide", name: "hq-safe-user-guide", component: UserGuidePage },
      { path: "functional-eval", name: "hq-safe-functional-eval", component: HQFunctionalEvalPage },
      { path: "functional-eval-monitoring", name: "hq-safe-functional-eval-monitoring", component: HQFunctionalEvalMonitoringPage },
      {
        path: "functional-eval-rewards-sanctions",
        name: "hq-safe-functional-eval-rewards-sanctions",
        component: HQFunctionalEvalRewardsSanctionsPage,
      },
      {
        path: "functional-eval/grade-report",
        name: "hq-safe-functional-eval-grade-report",
        component: HQFunctionalEvalGradeReportPage,
      },
      { path: "new-site-deployment", name: "hq-safe-new-site-deployment", component: HQNewSiteDeploymentPage },
      { path: "tbm-beta", name: "hq-safe-tbm-beta", component: TbmBetaPage },
      { path: "system-backup", name: "hq-safe-system-backup", component: HQSystemBackupPage },
      { path: "coupang-mvp-lab", name: "hq-safe-coupang-mvp-lab", component: CoupangMvpPage },
    ],
  },
  {
    path: "/site/functional-eval",
    component: FunctionalEvalLayout,
    meta: { requiresAuth: true, uiType: "SITE", requiresFunctionalEval: true },
    children: [
      { path: "", redirect: { name: "site-functional-eval-field-form-uploads" } },
      { path: "roster", name: "site-functional-eval-roster", component: SiteFunctionalEvalPage },
      { path: "evaluate", name: "site-functional-eval-evaluate", component: SiteFunctionalEvalPage },
      { path: "field-form-uploads", name: "site-functional-eval-field-form-uploads", component: FieldFormUploadPage },
      { path: "tbm-beta", name: "site-functional-eval-tbm-beta", component: TbmBetaPage },
      { path: "user-guide", name: "site-functional-eval-user-guide", component: UserGuidePage },
    ],
  },
  {
    path: "/site",
    component: SiteLayout,
    meta: { requiresAuth: true, uiType: "SITE" },
    children: [
      { path: "", redirect: { name: "site-field-form-uploads" } },
      { path: "field-form-uploads", name: "site-field-form-uploads", component: FieldFormUploadPage },
      { path: "dashboard", name: "site-dashboard", component: SiteDashboard },
      { path: "notices", name: "site-notices", component: SiteNoticeBoardPage },
      { path: "safety-policy-goals", name: "site-safety-policy-goals", component: SafetyPolicyGoalsPage },
      {
        path: "safety-education",
        name: "site-safety-education",
        component: SafetyEducationInspectionCalendarPage,
      },
      { path: "safety-inspections", redirect: { name: "site-safety-education" } },
      { path: "nonconformities", name: "site-nonconformities", component: NonconformityPage },
      { path: "worker-voice", name: "site-worker-voice", component: WorkerVoiceBoardPage },
      { path: "custom-menus/:slug", name: "site-dynamic-menu", component: DynamicMenuRuntimePage },
      { path: "documents", name: "site-documents", component: SiteDocumentsDashboardPage },
      { path: "document-explorer", name: "site-document-explorer", component: HQDocumentExplorerPage },
      { path: "documents/upload", name: "site-document-upload", component: DocumentUploadPage },
      { path: "communications", name: "site-communications", component: SiteCommunicationsPage },
      { path: "documents/:id", name: "site-document-detail", component: DocumentDetailPage },
      { path: "documents/:id/tbm-view", name: "site-document-tbm-view", component: RedirectLegacyTbmViewPage },
      {
        path: "mobile",
        component: SiteDailySafetyShellLayout,
        children: [
          { path: "", name: "site-mobile-ops", component: SiteMobileOpsPage },
          { path: "daily-capture", name: "site-mobile-daily-capture", component: SiteMobileDailyCapturePage },
          { path: "site-search", name: "site-mobile-site-search", component: SiteMobileSiteSearchPage },
          { path: "communications", name: "site-mobile-communications", component: SiteMobileCommunicationsPage },
        ],
      },
      { path: "risk-library", name: "site-risk-library", component: RiskLibraryPage },
      { path: "info", name: "site-info", component: SiteInfoPage },
      { path: "work-plan-forklift", name: "site-work-plan-forklift", component: WorkPlanForkliftPage },
      { path: "opinions", name: "site-opinions", component: OpinionListPage },
      { path: "opinions/:id", name: "site-opinion-detail", component: OpinionDetailPage },
      { path: "user-guide", name: "site-user-guide", component: UserGuidePage },
      { path: "new-site-deployment", name: "site-new-site-deployment", component: SiteNewSiteDeploymentPage },
    ],
  },
  {
    path: "/hq-other",
    component: HQOtherLayout,
    meta: { requiresAuth: true, uiType: "HQ_OTHER" },
    children: [
      { path: "", redirect: { name: "hq-other-field-form-uploads" } },
      { path: "field-form-uploads", name: "hq-other-field-form-uploads", component: FieldFormUploadPage },
      { path: "dashboard", name: "hq-other-dashboard", component: HQOtherDashboard },
      { path: "documents", name: "hq-other-documents", component: DocumentListPage },
      { path: "documents/:id", name: "hq-other-document-detail", component: DocumentDetailPage },
      { path: "documents/:id/tbm-view", name: "hq-other-document-tbm-view", component: RedirectLegacyTbmViewPage },
      { path: "functional-eval-monitoring", name: "hq-other-functional-eval-monitoring", component: HQFunctionalEvalMonitoringPage },
      { path: "opinions", name: "hq-other-opinions", component: OpinionListPage },
      { path: "opinions/:id", name: "hq-other-opinion-detail", component: OpinionDetailPage },
    ],
  },
  {
    path: "/documents/:id/tbm-view",
    name: "document-tbm-view",
    component: RedirectLegacyTbmViewPage,
    meta: { requiresAuth: true },
  },
  { path: "/dev/hq-test", name: "dev-hq-test", component: TestHQAdminPage, meta: { requiresAuth: true, devOnly: true, persona: "HQ_ADMIN" } },
  { path: "/dev/site-test", name: "dev-site-test", component: TestSiteManagerPage, meta: { requiresAuth: true, devOnly: true, persona: "SITE_MANAGER" } },
  { path: "/dev/worker-test", name: "dev-worker-test", component: TestWorkerPage, meta: { requiresAuth: true, devOnly: true, persona: "WORKER" } },
  {
    path: "/worker/mobile",
    name: "worker-mobile-list",
    component: WorkerMobileListPage,
  },
  {
    path: "/worker/mobile/:distributionId",
    name: "worker-mobile-detail",
    component: WorkerMobileDetailPage,
  },
  {
    path: "/:pathMatch(.*)*",
    redirect: "/",
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to, _from, next) => {
  const normalizedPath = normalizePublicSignPath(to.path);
  if (normalizedPath !== to.path) {
    next({ path: normalizedPath, query: to.query, hash: to.hash, replace: true });
    return;
  }
  if (to.meta.publicSign || isPublicSignPath(to.path)) {
    next();
    return;
  }

  const auth = useAuthStore();
  if (
    auth.token &&
    !auth.user &&
    !auth.sessionBootstrapped &&
    to.name !== "login" &&
    to.name !== "fe-onboarding"
  ) {
    await auth.bootstrapSession();
  }

  const workerAccessToken =
    typeof to.query.access_token === "string" && to.query.access_token.trim().length > 0
      ? to.query.access_token.trim()
      : null;

  if (
    (to.name === "worker-mobile-list" || to.name === "worker-mobile-detail") &&
    !auth.isAuthenticated &&
    !workerAccessToken
  ) {
    next({ name: "login", query: { redirect: to.fullPath } });
    return;
  }

  // dev route/persona 분기보다 먼저: 초기 비밀번호/동의 미완료 계정의 우회 진입 방지
  if (
    auth.isAuthenticated &&
    auth.needsFeOnboarding &&
    !isWeleraserReference(auth.user?.login_id) &&
    to.name !== "fe-onboarding"
  ) {
    next({ name: "fe-onboarding" });
    return;
  }
  // needsFeOnboarding이면 FeOnboardingPage에서 비밀번호/동의를 처리한다. change-password로 보내면 무한 redirect가 발생할 수 있다.
  if (
    auth.isAuthenticated &&
    auth.mustChangePassword &&
    !auth.needsFeOnboarding &&
    !isWeleraserReference(auth.user?.login_id) &&
    to.name !== "change-password"
  ) {
    next({ name: "change-password" });
    return;
  }

  if (to.meta.devOnly && !auth.isTestPersonaMode) {
    next({ name: "login" });
    return;
  }
  if (to.meta.devOnly && auth.isTestPersonaMode && !auth.effectivePersona) {
    next({ name: "persona-select" });
    return;
  }
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    next({ name: "login" });
    return;
  }

  const role = auth.user?.role || "";
  const isDeploymentTeam = role === "HQ_BUDGET_ESTIMATE" || role === "HQ_OUTSOURCING_PURCHASE";
  const goingDeployment = to.path.startsWith("/hq-safe/new-site-deployment");
  if (
    auth.isAuthenticated &&
    isDeploymentTeam &&
    !goingDeployment &&
    to.path !== "/change-password" &&
    to.path !== "/fe-onboarding" &&
    to.name !== "login"
  ) {
    next({ name: "hq-safe-new-site-deployment" });
    return;
  }

  const isFunctionalEvalUser = role === "SITE_FUNCTIONAL_EVAL";
  const goingFunctionalEval = to.path.startsWith("/site/functional-eval");
  const goingFunctionalEvalFieldForm = to.name === "site-functional-eval-field-form-uploads";
  if (goingFunctionalEval && !goingFunctionalEvalFieldForm && isMobileOpsSiteLogin(auth.user?.login_id)) {
    next({ name: siteMobileOrDesktopHomeName(auth.user?.login_id) });
    return;
  }
  if (
    auth.isAuthenticated &&
    isFunctionalEvalUser &&
    !goingFunctionalEval &&
    to.path !== "/change-password" &&
    to.path !== "/fe-onboarding" &&
    to.name !== "login"
  ) {
    next({ name: "site-functional-eval-field-form-uploads" });
    return;
  }

  const isFeViewer = isFunctionalEvalViewer(role);
  const goingFeViewerArea =
    to.path.startsWith("/hq-safe/functional-eval") ||
    to.path.startsWith("/hq-safe/functional-eval-monitoring") ||
    to.name === "hq-safe-functional-eval-grade-report";
  if (
    auth.isAuthenticated &&
    isFeViewer &&
    !goingFeViewerArea &&
    to.path !== "/change-password" &&
    to.path !== "/fe-onboarding" &&
    to.name !== "login"
  ) {
    next({ name: "hq-safe-functional-eval" });
    return;
  }

  if (to.meta.requiresPdfSigning && !canAccessHqSafeWorkspace(auth.user?.role)) {
    if (auth.user?.ui_type === "HQ_SAFE") next({ name: hqSafeHomeRouteName() });
    else if (auth.user?.ui_type === "SITE") next({ name: siteMobileOrDesktopHomeName(auth.user?.login_id) });
    else if (auth.user?.ui_type === "HQ_OTHER") next({ name: "hq-other-field-form-uploads" });
    else next({ name: "login" });
    return;
  }
  if (to.meta.requiresAccidentAdmin && !canAccessHqSafeWorkspace(auth.user?.role)) {
    if (auth.user?.ui_type === "HQ_SAFE") next({ name: hqSafeHomeRouteName() });
    else if (auth.user?.ui_type === "SITE") next({ name: siteMobileOrDesktopHomeName(auth.user?.login_id) });
    else if (auth.user?.ui_type === "HQ_OTHER") next({ name: "hq-other-field-form-uploads" });
    else next({ name: "login" });
    return;
  }
  if (to.name === "hq-safe-accidents" && typeof window !== "undefined") {
    const stored = window.localStorage.getItem("besma_accident_prefer_worklist");
    const preferWorklist = stored == null ? true : stored === "true";
    if (preferWorklist && to.query.bypassWorklist !== "1") {
      next({ name: "hq-safe-accidents-worklist" });
      return;
    }
  }

  if (auth.isAuthenticated && auth.isTestPersonaMode) {
    if (to.name === "login") {
      if (auth.effectivePersona === "WORKER") {
        next({ name: "worker-mobile-list" });
        return;
      }
      if (auth.effectivePersona === "SITE_MANAGER") {
        next({ name: siteMobileOrDesktopHomeName(auth.user?.login_id) });
        return;
      }
      if (auth.effectiveUiType === "HQ_SAFE") {
        next({ name: hqSafeHomeRouteName() });
        return;
      }
      if (auth.user?.role === "WORKER") next({ name: "worker-mobile-list" });
      else if (auth.user?.ui_type === "HQ_SAFE") next({ name: hqSafeHomeRouteName() });
      else if (auth.user?.ui_type === "SITE") next({ name: siteMobileOrDesktopHomeName(auth.user?.login_id) });
      else if (auth.user?.ui_type === "HQ_OTHER") next({ name: "hq-other-field-form-uploads" });
      else next();
      return;
    }

    if (to.meta.persona && auth.effectivePersona && to.meta.persona !== auth.effectivePersona) {
      if (auth.effectivePersona === "HQ_ADMIN") next({ name: hqSafeHomeRouteName() });
      else if (auth.effectivePersona === "SITE_MANAGER") next({ name: siteMobileOrDesktopHomeName(auth.user?.login_id) });
      else next({ name: "worker-mobile-list" });
      return;
    }

    if (to.meta.uiType && auth.effectiveUiType && to.meta.uiType !== auth.effectiveUiType && !isWeleraserReference(auth.user?.login_id)) {
      if (auth.effectivePersona === "WORKER") next({ name: "worker-mobile-list" });
      else if (auth.effectiveUiType === "HQ_SAFE") next({ name: hqSafeHomeRouteName() });
      else if (auth.effectiveUiType === "SITE") next({ name: siteMobileOrDesktopHomeName(auth.user?.login_id) });
      else next({ name: "hq-other-field-form-uploads" });
      return;
    }
  } else if (to.meta.uiType && auth.user && auth.user.ui_type !== to.meta.uiType) {
    if (auth.user.role === "WORKER") next({ name: "worker-mobile-list" });
    else if (!isWeleraserReference(auth.user?.login_id) && auth.user.ui_type === "HQ_SAFE") next({ name: hqSafeHomeRouteName() });
    else if (!isWeleraserReference(auth.user?.login_id) && auth.user.ui_type === "SITE") next({ name: siteMobileOrDesktopHomeName(auth.user?.login_id) });
    else if (auth.user.ui_type === "HQ_OTHER") next({ name: "hq-other-field-form-uploads" });
    else next({ name: "login" });
    return;
  }

  if (to.name === "login" && auth.isAuthenticated) {
    if (auth.needsFeOnboarding && !isWeleraserReference(auth.user?.login_id)) {
      next({ name: "fe-onboarding" });
      return;
    }
    if (auth.mustChangePassword && !isWeleraserReference(auth.user?.login_id)) {
      next({ name: "change-password" });
      return;
    }
    if (auth.isTestPersonaMode) {
      if (auth.effectivePersona === "HQ_ADMIN") next({ name: hqSafeHomeRouteName() });
      else if (auth.effectivePersona === "SITE_MANAGER") next({ name: siteMobileOrDesktopHomeName(auth.user?.login_id) });
      else if (auth.effectivePersona === "WORKER") next({ name: "worker-mobile-list" });
      else if (auth.user?.role === "WORKER") next({ name: "worker-mobile-list" });
      else if (auth.user?.ui_type === "HQ_SAFE") next({ name: hqSafeHomeRouteName() });
      else if (auth.user?.ui_type === "SITE") next({ name: siteMobileOrDesktopHomeName(auth.user?.login_id) });
      else if (auth.user?.ui_type === "HQ_OTHER") next({ name: "hq-other-field-form-uploads" });
      else next();
    } else if (auth.user?.role === "WORKER") next({ name: "worker-mobile-list" });
    else if (auth.user?.role === "SITE_FUNCTIONAL_EVAL") next({ name: "site-functional-eval-field-form-uploads" });
    else if (auth.user?.role === "HQ_BUDGET_ESTIMATE" || auth.user?.role === "HQ_OUTSOURCING_PURCHASE")
      next({ name: "hq-safe-new-site-deployment" });
    else if (auth.user?.ui_type === "HQ_SAFE") next({ name: hqSafeHomeRouteName() });
    else if (auth.user?.ui_type === "SITE") next({ name: siteMobileOrDesktopHomeName(auth.user?.login_id) });
    else if (auth.user?.ui_type === "HQ_OTHER") next({ name: "hq-other-field-form-uploads" });
    else next();
    return;
  }

  next();
});



