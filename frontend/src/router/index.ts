import { createRouter, createWebHistory, RouteRecordRaw } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import LoginPage from "@/pages/LoginPage.vue";
import HQSafeLayout from "@/layouts/HQSafeLayout.vue";
import SiteLayout from "@/layouts/SiteLayout.vue";
import HQOtherLayout from "@/layouts/HQOtherLayout.vue";
import HQSafeDashboard from "@/pages/dashboard/HQSafeDashboard.vue";
import SiteDashboard from "@/pages/dashboard/SiteDashboard.vue";
import HQOtherDashboard from "@/pages/dashboard/HQOtherDashboard.vue";
import DocumentListPage from "@/pages/documents/DocumentListPage.vue";
import DocumentDetailPage from "@/pages/documents/DocumentDetailPage.vue";
import DocumentUploadPage from "@/pages/documents/DocumentUploadPage.vue";
import DocumentTbmViewPage from "@/pages/documents/DocumentTbmViewPage.vue";
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
import SiteMobileOpsPage from "@/pages/site/SiteMobileOpsPage.vue";
import HQTbmMonitorPage from "@/pages/hq/HQTbmMonitorPage.vue";
import HQWorkerSafetyRecordPage from "@/pages/hq/HQWorkerSafetyRecordPage.vue";
import HQDocumentsDashboardPage from "@/pages/hq/HQDocumentsDashboardPage.vue";
import HQDocumentExplorerPage from "@/pages/hq/HQDocumentExplorerPage.vue";
import HQPendingDocumentsPage from "@/pages/hq/HQPendingDocumentsPage.vue";
import HQSitesPage from "@/pages/hq/HQSitesPage.vue";
import HQUsersPage from "@/pages/hq/HQUsersPage.vue";
import HQDocumentSettingsPage from "@/pages/hq/HQDocumentSettingsPage.vue";
import HQContractorDocumentBundleSettingsPage from "@/pages/hq/HQContractorDocumentBundleSettingsPage.vue";
import RiskLibraryPage from "@/pages/risk/RiskLibraryPage.vue";
import SiteDocumentsDashboardPage from "@/pages/site/SiteDocumentsDashboardPage.vue";
import SiteCommunicationsPage from "@/pages/site/SiteCommunicationsPage.vue";
import SiteMobileCommunicationsPage from "@/pages/site/SiteMobileCommunicationsPage.vue";
import SiteMobileSiteSearchPage from "@/pages/site/SiteMobileSiteSearchPage.vue";
import SiteInfoPage from "@/pages/site/SiteInfoPage.vue";
import ChangePasswordPage from "@/pages/auth/ChangePasswordPage.vue";

const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "login",
    component: LoginPage,
  },
  {
    path: "/change-password",
    name: "change-password",
    component: ChangePasswordPage,
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
      { path: "dashboard", name: "hq-safe-dashboard", component: HQSafeDashboard },
      { path: "documents", name: "hq-safe-documents", component: HQDocumentsDashboardPage },
      { path: "document-explorer", name: "hq-safe-document-explorer", component: HQDocumentExplorerPage },
      { path: "documents/pending-review", name: "hq-safe-documents-pending", component: HQPendingDocumentsPage },
      { path: "documents/:id", name: "hq-safe-document-detail", component: DocumentDetailPage },
      { path: "documents/:id/tbm-view", name: "hq-safe-document-tbm-view", component: DocumentTbmViewPage },
      { path: "approvals/inbox", name: "hq-safe-approval-inbox", component: ApprovalInboxPage },
      {
        path: "approvals/history",
        name: "hq-safe-approval-history",
        component: ApprovalHistoryPage,
      },
      { path: "tbm-monitor", name: "hq-safe-tbm-monitor", component: HQTbmMonitorPage },
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
    ],
  },
  {
    path: "/site",
    component: SiteLayout,
    meta: { requiresAuth: true, uiType: "SITE" },
    children: [
      { path: "dashboard", name: "site-dashboard", component: SiteDashboard },
      { path: "documents", name: "site-documents", component: SiteDocumentsDashboardPage },
      { path: "document-explorer", name: "site-document-explorer", component: HQDocumentExplorerPage },
      { path: "documents/upload", name: "site-document-upload", component: DocumentUploadPage },
      { path: "communications", name: "site-communications", component: SiteCommunicationsPage },
      { path: "documents/:id", name: "site-document-detail", component: DocumentDetailPage },
      { path: "documents/:id/tbm-view", name: "site-document-tbm-view", component: DocumentTbmViewPage },
      { path: "mobile", name: "site-mobile-ops", component: SiteMobileOpsPage },
      { path: "mobile/site-search", name: "site-mobile-site-search", component: SiteMobileSiteSearchPage },
      { path: "mobile/communications", name: "site-mobile-communications", component: SiteMobileCommunicationsPage },
      { path: "risk-library", name: "site-risk-library", component: RiskLibraryPage },
      { path: "info", name: "site-info", component: SiteInfoPage },
      { path: "opinions", name: "site-opinions", component: OpinionListPage },
      { path: "opinions/:id", name: "site-opinion-detail", component: OpinionDetailPage },
    ],
  },
  {
    path: "/hq-other",
    component: HQOtherLayout,
    meta: { requiresAuth: true, uiType: "HQ_OTHER" },
    children: [
      { path: "dashboard", name: "hq-other-dashboard", component: HQOtherDashboard },
      { path: "documents", name: "hq-other-documents", component: DocumentListPage },
      { path: "documents/:id", name: "hq-other-document-detail", component: DocumentDetailPage },
      { path: "documents/:id/tbm-view", name: "hq-other-document-tbm-view", component: DocumentTbmViewPage },
      { path: "opinions", name: "hq-other-opinions", component: OpinionListPage },
      { path: "opinions/:id", name: "hq-other-opinion-detail", component: OpinionDetailPage },
    ],
  },
  {
    path: "/documents/:id/tbm-view",
    name: "document-tbm-view",
    component: DocumentTbmViewPage,
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
    redirect: "/login",
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore();
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

  if (to.meta.devOnly && !auth.isTestPersonaMode) {
    next({ name: "login" });
    return;
  }
  if (to.meta.devOnly && auth.isTestPersonaMode && !auth.effectivePersona) {
    next({ name: "persona-select" });
    return;
  }

  if (auth.isAuthenticated && auth.mustChangePassword && to.path !== "/change-password") {
    next({ name: "change-password" });
    return;
  }
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    next({ name: "login" });
    return;
  }

  if (auth.isAuthenticated && auth.isTestPersonaMode) {
    if (to.name === "login") {
      if (auth.effectivePersona === "WORKER") {
        next({ name: "worker-mobile-list" });
        return;
      }
      if (auth.effectivePersona === "SITE_MANAGER") {
        next({ name: "site-mobile-ops" });
        return;
      }
      if (auth.effectiveUiType === "HQ_SAFE") {
        next({ name: "hq-safe-tbm-monitor" });
        return;
      }
      if (auth.user?.role === "WORKER") next({ name: "worker-mobile-list" });
      else if (auth.user?.ui_type === "HQ_SAFE") next({ name: "hq-safe-tbm-monitor" });
      else if (auth.user?.ui_type === "SITE") next({ name: "site-mobile-ops" });
      else if (auth.user?.ui_type === "HQ_OTHER") next({ name: "hq-other-dashboard" });
      else next();
      return;
    }

    if (to.meta.persona && auth.effectivePersona && to.meta.persona !== auth.effectivePersona) {
      if (auth.effectivePersona === "HQ_ADMIN") next({ name: "hq-safe-tbm-monitor" });
      else if (auth.effectivePersona === "SITE_MANAGER") next({ name: "site-mobile-ops" });
      else next({ name: "worker-mobile-list" });
      return;
    }

    if (to.meta.uiType && auth.effectiveUiType && to.meta.uiType !== auth.effectiveUiType) {
      if (auth.effectivePersona === "WORKER") next({ name: "worker-mobile-list" });
      else if (auth.effectiveUiType === "HQ_SAFE") next({ name: "hq-safe-tbm-monitor" });
      else if (auth.effectiveUiType === "SITE") next({ name: "site-mobile-ops" });
      else next({ name: "hq-other-dashboard" });
      return;
    }
  } else if (to.meta.uiType && auth.user && auth.user.ui_type !== to.meta.uiType) {
    if (auth.user.role === "WORKER") next({ name: "worker-mobile-list" });
    else if (auth.user.ui_type === "HQ_SAFE") next({ name: "hq-safe-tbm-monitor" });
    else if (auth.user.ui_type === "SITE") next({ name: "site-mobile-ops" });
    else if (auth.user.ui_type === "HQ_OTHER") next({ name: "hq-other-dashboard" });
    else next({ name: "login" });
    return;
  }

  if (to.name === "login" && auth.isAuthenticated) {
    if (auth.isTestPersonaMode) {
      if (auth.effectivePersona === "HQ_ADMIN") next({ name: "hq-safe-tbm-monitor" });
      else if (auth.effectivePersona === "SITE_MANAGER") next({ name: "site-mobile-ops" });
      else if (auth.effectivePersona === "WORKER") next({ name: "worker-mobile-list" });
      else if (auth.user?.role === "WORKER") next({ name: "worker-mobile-list" });
      else if (auth.user?.ui_type === "HQ_SAFE") next({ name: "hq-safe-tbm-monitor" });
      else if (auth.user?.ui_type === "SITE") next({ name: "site-mobile-ops" });
      else if (auth.user?.ui_type === "HQ_OTHER") next({ name: "hq-other-dashboard" });
      else next();
    } else if (auth.user?.role === "WORKER") next({ name: "worker-mobile-list" });
    else if (auth.user?.ui_type === "HQ_SAFE") next({ name: "hq-safe-tbm-monitor" });
    else if (auth.user?.ui_type === "SITE") next({ name: "site-mobile-ops" });
    else if (auth.user?.ui_type === "HQ_OTHER") next({ name: "hq-other-dashboard" });
    else next();
    return;
  }

  next();
});

