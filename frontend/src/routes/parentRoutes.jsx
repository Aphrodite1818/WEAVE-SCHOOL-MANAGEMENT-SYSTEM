import { Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import ParentAttendancePage from "../pages/parent/ParentAttendancePage";
import ParentDashboardPage from "../pages/parent/ParentDashboardPage";
import ParentReportCardsPage from "../pages/parent/ParentReportCardsPage";
import ParentResultsPage from "../pages/parent/ParentResultsPage";
import ParentStudentLinkingPage from "../pages/parent/ParentStudentLinkingPage";
import CommunicationInboxPage from "../pages/shared/CommunicationInboxPage";
import MessagesPage from "../pages/shared/MessagesPage";
import RoleGettingStartedPage from "../pages/shared/RoleGettingStartedPage";
import RoleSettingsPage from "../pages/shared/RoleSettingsPage";
import SchoolCalendarPage from "../pages/shared/SchoolCalendarPage";
import SchoolSwitchPage from "../pages/shared/SchoolSwitchPage";
import MembershipScopeGuard from "./MembershipScopeGuard";
import RoleGuard from "./RoleGuard";
import RuntimeFeatureRoute from "./RuntimeFeatureRoute";

export const parentRoutes = (
  <Route element={<RoleGuard allowedRoles={["PARENT"]} />}>
    <Route element={<DashboardShell role="parent" onboardingModalEnabled={false} />}>
      <Route path="/parent/schools" element={<SchoolSwitchPage role="parent" />} />
    </Route>

    <Route element={<MembershipScopeGuard role="parent" />}>
      <Route element={<DashboardShell role="parent" />}>
        <Route path="/parent/dashboard" element={<ParentDashboardPage />} />
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
