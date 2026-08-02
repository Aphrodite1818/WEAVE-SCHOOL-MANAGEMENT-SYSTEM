import { Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import SuperadminAnalyticsPage from "../pages/superadmin/SuperadminAnalyticsPage";
import SuperadminControlCenterPage from "../pages/superadmin/SuperadminControlCenterPage";
import SuperadminDashboardPage from "../pages/superadmin/SuperadminDashboardPage";
import SuperadminSettingsPage from "../pages/superadmin/SuperadminSettingsPage";
import SuperadminTenantUsagePage from "../pages/superadmin/SuperadminTenantUsagePage";
import SuperadminTrafficMonitorPage from "../pages/superadmin/SuperadminTrafficMonitorPage";
import AnnouncementManagementPage from "../pages/shared/AnnouncementManagementPage";
import CommunicationInboxPage from "../pages/shared/CommunicationInboxPage";
import MessagesPage from "../pages/shared/MessagesPage";
import SchoolCalendarPage from "../pages/shared/SchoolCalendarPage";
import RoleGuard from "./RoleGuard";
import RuntimeFeatureRoute from "./RuntimeFeatureRoute";

export const superadminRoutes = (
  <Route element={<RoleGuard allowedRoles={["SUPERADMIN"]} />}>
    <Route element={<DashboardShell role="superadmin" />}>
      <Route path="/superadmin/dashboard" element={<SuperadminDashboardPage />} />
      <Route path="/superadmin/analytics" element={<SuperadminAnalyticsPage />} />
      <Route path="/superadmin/control-center" element={<SuperadminControlCenterPage />} />
      <Route path="/superadmin/usage" element={<SuperadminTenantUsagePage />} />
      <Route path="/superadmin/traffic" element={<SuperadminTrafficMonitorPage />} />
      <Route path="/superadmin/calendar" element={<SchoolCalendarPage role="superadmin" />} />
      <Route path="/superadmin/inbox" element={<CommunicationInboxPage />} />
      <Route path="/superadmin/messages" element={<RuntimeFeatureRoute feature="messaging" role="superadmin"><MessagesPage /></RuntimeFeatureRoute>} />
      <Route path="/superadmin/announcements" element={<AnnouncementManagementPage mode="superadmin" />} />
      <Route path="/superadmin/settings" element={<SuperadminSettingsPage />} />
    </Route>
  </Route>
);
