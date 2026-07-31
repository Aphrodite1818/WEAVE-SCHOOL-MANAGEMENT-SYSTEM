import { Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import PullRefreshBoundary from "../components/layout/PullRefreshBoundary";
import AcademicHubOverviewPage from "../pages/admin/AcademicHubOverviewPage";
import AcademicWorkflowPage from "../pages/admin/AcademicWorkflowPage";
import AdminDashboardPage from "../pages/admin/AdminDashboardPage";
import AdminInvitationPage from "../pages/admin/AdminInvitationPage";
import AdminSearchDetailPage from "../pages/admin/AdminSearchDetailPage";
import AttendancePage from "../pages/admin/AttendancePage";
import BillingPage from "../pages/admin/BillingPage";
import ParentLinkManagementPage from "../pages/admin/ParentLinkManagementPage";
import ParentsPage from "../pages/admin/ParentsPage";
import StudentCreatePage from "../pages/admin/StudentCreatePage";
import StudentSlipsPage from "../pages/admin/StudentSlipsPage";
import StudentsPage from "../pages/admin/StudentsPage";
import SubscriptionOptionsPage from "../pages/admin/SubscriptionOptionsPage";
import SubscriptionVerifyPage from "../pages/admin/SubscriptionVerifyPage";
import TeachersPage from "../pages/admin/TeachersPage";
import UsagePage from "../pages/admin/UsagePage";
import AnnouncementManagementPage from "../pages/shared/AnnouncementManagementPage";
import CommunicationInboxPage from "../pages/shared/CommunicationInboxPage";
import MessagesPage from "../pages/shared/MessagesPage";
import RoleAnalyticsPage from "../pages/shared/RoleAnalyticsPage";
import SchoolCalendarPage from "../pages/shared/SchoolCalendarPage";
import RoleSettingsPage from "../pages/shared/RoleSettingsPage";
import BulkImportRouteGuard from "./BulkImportRouteGuard";
import RoleGuard from "./RoleGuard";
import RuntimeFeatureRoute from "./RuntimeFeatureRoute";

const protectedWorkflow = (element) => (
  <PullRefreshBoundary>{element}</PullRefreshBoundary>
);

export const adminRoutes = (
  <Route element={<RoleGuard allowedRoles={["ADMIN"]} />}>
    <Route path="/admin/billing/plans" element={<SubscriptionOptionsPage />} />
    <Route path="/billing/subscription/verify" element={<SubscriptionVerifyPage />} />

    <Route element={<DashboardShell role="admin" />}>
      <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
      <Route path="/admin/search/:resultKey" element={<AdminSearchDetailPage />} />
      <Route path="/admin/analytics" element={<RoleAnalyticsPage role="admin" />} />
      <Route path="/admin/calendar" element={<SchoolCalendarPage role="admin" />} />
      <Route path="/admin/invitations/:role" element={protectedWorkflow(<AdminInvitationPage />)} />
      <Route path="/admin/teachers" element={protectedWorkflow(<TeachersPage />)} />
      <Route path="/admin/students" element={protectedWorkflow(<StudentsPage />)} />
      <Route path="/admin/students/create" element={protectedWorkflow(<StudentCreatePage />)} />
      <Route path="/admin/parents" element={protectedWorkflow(<ParentsPage />)} />
      <Route path="/admin/parents/links" element={protectedWorkflow(<ParentLinkManagementPage />)} />
      <Route path="/admin/imports" element={protectedWorkflow(<BulkImportRouteGuard />)} />
      <Route path="/admin/imports/:jobId/student-slips" element={protectedWorkflow(<BulkImportRouteGuard><StudentSlipsPage /></BulkImportRouteGuard>)} />
      <Route path="/admin/imports/:step" element={protectedWorkflow(<BulkImportRouteGuard />)} />
      <Route path="/admin/imports/:step/:jobId" element={protectedWorkflow(<BulkImportRouteGuard />)} />
      <Route path="/admin/attendance" element={<RuntimeFeatureRoute feature="attendance" role="admin">{protectedWorkflow(<AttendancePage />)}</RuntimeFeatureRoute>} />
      <Route path="/admin/academic" element={<AcademicHubOverviewPage />} />
      <Route path="/admin/academic/:workflow" element={protectedWorkflow(<AcademicWorkflowPage />)} />
      <Route path="/admin/billing" element={<BillingPage />} />
      <Route path="/admin/usage" element={<UsagePage />} />
      <Route path="/admin/inbox" element={<CommunicationInboxPage />} />
      <Route path="/admin/messages" element={<RuntimeFeatureRoute feature="messaging" role="admin"><MessagesPage /></RuntimeFeatureRoute>} />
      <Route path="/admin/announcements" element={<AnnouncementManagementPage mode="tenant-admin" />} />
      <Route path="/admin/settings" element={<RoleSettingsPage role="admin" />} />
    </Route>
  </Route>
);
