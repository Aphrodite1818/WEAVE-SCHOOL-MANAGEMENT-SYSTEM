import { Navigate, Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import AcademicHubOverviewPage from "../pages/admin/AcademicHubOverviewPage";
import AcademicWorkflowPage from "../pages/admin/AcademicWorkflowPage";
import AdminDashboardPage from "../pages/admin/AdminDashboardPage";
import AdminInvitationPage from "../pages/admin/AdminInvitationPage";
import AdminSearchDetailPage from "../pages/admin/AdminSearchDetailPage";
import AttendancePage from "../pages/admin/AttendancePage";
import BillingPage from "../pages/admin/BillingPage";
import CreateUserPage from "../pages/admin/CreateUserPage";
import FeesPage from "../pages/admin/FeesPage";
import ParentsPage from "../pages/admin/ParentsPage";
import PaymentsPage from "../pages/admin/PaymentsPage";
import StudentsPage from "../pages/admin/StudentsPage";
import SubscriptionOptionsPage from "../pages/admin/SubscriptionOptionsPage";
import SubscriptionVerifyPage from "../pages/admin/SubscriptionVerifyPage";
import TeachersPage from "../pages/admin/TeachersPage";
import UsagePage from "../pages/admin/UsagePage";
import AnnouncementsWorkspacePage from "../pages/shared/AnnouncementsWorkspacePage";
import RoleAnalyticsPage from "../pages/shared/RoleAnalyticsPage";
import RoleSettingsPage from "../pages/shared/RoleSettingsPage";
import StaticModulePage from "../pages/shared/StaticModulePage";
import BulkImportRouteGuard from "./BulkImportRouteGuard";
import RoleGuard from "./RoleGuard";

export const adminRoutes = (
  <Route element={<RoleGuard allowedRoles={["ADMIN"]} />}>
    <Route path="/admin/billing/plans" element={<SubscriptionOptionsPage />} />
    <Route
      path="/billing/subscription/verify"
      element={<SubscriptionVerifyPage />}
    />

    <Route element={<DashboardShell role="admin" />}>
      <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
      <Route
        path="/admin/search/:resultKey"
        element={<AdminSearchDetailPage />}
      />
      <Route
        path="/admin/analytics"
        element={<RoleAnalyticsPage role="admin" />}
      />
      <Route path="/admin/create-user" element={<CreateUserPage />} />
      <Route
        path="/admin/invitations/:role"
        element={<AdminInvitationPage />}
      />
      <Route path="/admin/teachers" element={<TeachersPage />} />
      <Route path="/admin/students" element={<StudentsPage />} />
      <Route path="/admin/parents" element={<ParentsPage />} />
      <Route
        path="/admin/classes"
        element={<Navigate to="/admin/academic/class-subjects" replace />}
      />
      <Route
        path="/admin/subjects"
        element={<Navigate to="/admin/academic/setup?tab=subjects" replace />}
      />
      <Route path="/admin/imports" element={<BulkImportRouteGuard />} />
      <Route path="/admin/attendance" element={<AttendancePage />} />
      <Route
        path="/admin/exams"
        element={<Navigate to="/admin/academic" replace />}
      />
      <Route
        path="/admin/results"
        element={<Navigate to="/admin/academic/results" replace />}
      />
      <Route path="/admin/academic" element={<AcademicHubOverviewPage />} />
      <Route
        path="/admin/academic/manage"
        element={<Navigate to="/admin/academic" replace />}
      />
      <Route
        path="/admin/academic/:workflow"
        element={<AcademicWorkflowPage />}
      />
      <Route path="/admin/fees" element={<FeesPage />} />
      <Route path="/admin/payments" element={<PaymentsPage />} />
      <Route path="/admin/billing" element={<BillingPage />} />
      <Route path="/admin/usage" element={<UsagePage />} />
      <Route
        path="/admin/timetable"
        element={
          <StaticModulePage
            role="admin"
            title="Timetable"
            description="Professional schedule grid and class timetable planning."
            type="timetable"
          />
        }
      />
      <Route
        path="/admin/announcements"
        element={<AnnouncementsWorkspacePage mode="tenant-admin" />}
      />
      <Route
        path="/admin/messages"
        element={
          <AnnouncementsWorkspacePage
            mode="tenant-admin"
            variant="messages"
          />
        }
      />
      <Route
        path="/admin/reports"
        element={
          <StaticModulePage
            role="admin"
            title="Reports"
            description="Operational reports will appear here when backend reporting endpoints are available."
            type="settings"
          />
        }
      />
      <Route
        path="/admin/settings"
        element={<RoleSettingsPage role="admin" />}
      />
    </Route>
  </Route>
);
