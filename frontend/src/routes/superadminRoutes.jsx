/* eslint-disable react-refresh/only-export-components */

import { lazy } from "react";
import { Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import RoleGuard from "./RoleGuard";
import RuntimeFeatureRoute from "./RuntimeFeatureRoute";

const SuperadminAnalyticsPage = lazy(() => import("../pages/superadmin/SuperadminAnalyticsPage"));
const SuperadminControlCenterPage = lazy(() => import("../pages/superadmin/SuperadminControlCenterPage"));
const SuperadminDashboardPage = lazy(() => import("../pages/superadmin/SuperadminDashboardPage"));
const SuperadminSettingsPage = lazy(() => import("../pages/superadmin/SuperadminSettingsPage"));
const SuperadminSimulationPage = lazy(() => import("../pages/superadmin/SuperadminSimulationPage"));
const SuperadminTenantUsagePage = lazy(() => import("../pages/superadmin/SuperadminTenantUsagePage"));
const SuperadminTrafficMonitorPage = lazy(() => import("../pages/superadmin/SuperadminTrafficMonitorPage"));
const SuperadminCBTResultOperationsPage = lazy(() => import("../pages/superadmin/SuperadminCBTResultOperationsPage"));
const NoticeManagementPage = lazy(() => import("../pages/shared/NoticeManagementPage"));
const CommunicationInboxPage = lazy(() => import("../pages/shared/CommunicationInboxPage"));
const MessagesPage = lazy(() => import("../pages/shared/MessagesPage"));
const SchoolCalendarPage = lazy(() => import("../pages/shared/SchoolCalendarPage"));

export const superadminRoutes = (
  <Route element={<RoleGuard allowedRoles={["SUPERADMIN"]} />}>
    <Route element={<DashboardShell role="superadmin" />}>
      <Route path="/superadmin/dashboard" element={<SuperadminDashboardPage />} />
      <Route path="/superadmin/analytics" element={<SuperadminAnalyticsPage />} />
      <Route path="/superadmin/control-center" element={<SuperadminControlCenterPage />} />
      <Route path="/superadmin/verification" element={<SuperadminControlCenterPage />} />
      <Route path="/superadmin/usage" element={<SuperadminTenantUsagePage />} />
      <Route path="/superadmin/traffic" element={<SuperadminTrafficMonitorPage />} />
      <Route path="/superadmin/cbt-results" element={<SuperadminCBTResultOperationsPage />} />
      <Route path="/superadmin/simulations" element={<RuntimeFeatureRoute feature="simulations" role="superadmin"><SuperadminSimulationPage /></RuntimeFeatureRoute>} />
      <Route path="/superadmin/calendar" element={<SchoolCalendarPage role="superadmin" />} />
      <Route path="/superadmin/inbox" element={<CommunicationInboxPage />} />
      <Route path="/superadmin/messages" element={<RuntimeFeatureRoute feature="messaging" role="superadmin"><MessagesPage /></RuntimeFeatureRoute>} />
      <Route path="/superadmin/notices" element={<NoticeManagementPage mode="superadmin" />} />
      <Route path="/superadmin/settings" element={<SuperadminSettingsPage />} />
    </Route>
  </Route>
);
