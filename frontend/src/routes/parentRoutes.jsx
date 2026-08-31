/* eslint-disable react-refresh/only-export-components */

import { lazy } from "react";
import { Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import MembershipScopeGuard from "./MembershipScopeGuard";
import RoleGuard from "./RoleGuard";
import RuntimeFeatureRoute from "./RuntimeFeatureRoute";

const ParentAttendancePage = lazy(() => import("../pages/parent/ParentAttendancePage"));
const ParentDashboardPage = lazy(() => import("../pages/parent/ParentDashboardPage"));
const ParentReportCardsPage = lazy(() => import("../pages/parent/ParentReportCardsPage"));
const ParentResultsPage = lazy(() => import("../pages/parent/ParentResultsPage"));
const ParentStudentLinkingPage = lazy(() => import("../pages/parent/ParentStudentLinkingPage"));
const CommunicationInboxPage = lazy(() => import("../pages/shared/CommunicationInboxPage"));
const MessagesPage = lazy(() => import("../pages/shared/MessagesPage"));
const RoleAnalyticsPage = lazy(() => import("../pages/shared/RoleAnalyticsPage"));
const RoleGettingStartedPage = lazy(() => import("../pages/shared/RoleGettingStartedPage"));
const RoleSettingsPage = lazy(() => import("../pages/shared/RoleSettingsPage"));
const SchoolCalendarPage = lazy(() => import("../pages/shared/SchoolCalendarPage"));
const SchoolSwitchPage = lazy(() => import("../pages/shared/SchoolSwitchPage"));

export const parentRoutes = (
  <Route element={<RoleGuard allowedRoles={["PARENT"]} />}>
    <Route element={<DashboardShell role="parent" onboardingModalEnabled={false} />}>
      <Route path="/parent/schools" element={<SchoolSwitchPage role="parent" />} />
    </Route>
    <Route element={<MembershipScopeGuard role="parent" />}>
      <Route element={<DashboardShell role="parent" />}>
        <Route path="/parent/dashboard" element={<ParentDashboardPage />} />
        <Route path="/parent/analytics" element={<RoleAnalyticsPage role="parent" />} />
        <Route path="/parent/getting-started" element={<RoleGettingStartedPage role="parent" />} />
        <Route path="/parent/student-linking" element={<ParentStudentLinkingPage />} />
        <Route path="/parent/report-cards" element={<ParentReportCardsPage />} />
        <Route path="/parent/attendance" element={<RuntimeFeatureRoute feature="attendance" role="parent"><ParentAttendancePage /></RuntimeFeatureRoute>} />
        <Route path="/parent/calendar" element={<SchoolCalendarPage role="parent" />} />
        <Route path="/parent/results" element={<ParentResultsPage />} />
        <Route path="/parent/inbox" element={<CommunicationInboxPage />} />
        <Route path="/parent/messages" element={<RuntimeFeatureRoute feature="messaging" role="parent"><MessagesPage /></RuntimeFeatureRoute>} />
        <Route path="/parent/settings" element={<RoleSettingsPage role="parent" />} />
      </Route>
    </Route>
  </Route>
);
