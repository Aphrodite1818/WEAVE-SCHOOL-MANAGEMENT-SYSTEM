import { Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import SuperadminAnalyticsPage from "../pages/superadmin/SuperadminAnalyticsPage";
import SuperadminDashboardPage from "../pages/superadmin/SuperadminDashboardPage";
import AnnouncementsWorkspacePage from "../pages/shared/AnnouncementsWorkspacePage";
import StaticModulePage from "../pages/shared/StaticModulePage";
import RoleGuard from "./RoleGuard";

export const superadminRoutes = (
  <Route element={<RoleGuard allowedRoles={["SUPERADMIN"]} />}>
    <Route element={<DashboardShell role="superadmin" />}>
      <Route path="/superadmin/dashboard" element={<SuperadminDashboardPage />} />
      <Route path="/superadmin/analytics" element={<SuperadminAnalyticsPage />} />
      <Route path="/superadmin/announcements" element={<AnnouncementsWorkspacePage mode="superadmin" />} />
      <Route path="/superadmin/verification" element={<StaticModulePage role="superadmin" title="Verification" description="Tenant verification activity and approval workflow." type="settings" />} />
      <Route path="/superadmin/activity" element={<StaticModulePage role="superadmin" title="Platform Activity" description="Recent registrations, verification events, and system statistics." type="ai" />} />
      <Route path="/superadmin/settings" element={<StaticModulePage role="superadmin" title="Platform Settings" description="Platform-wide configuration and administrator controls." type="settings" />} />
    </Route>
  </Route>
);
