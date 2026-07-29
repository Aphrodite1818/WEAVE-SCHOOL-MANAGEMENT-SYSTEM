import { Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import ParentDashboardPage from "../pages/parent/ParentDashboardPage";
import ParentResultsPage from "../pages/parent/ParentResultsPage";
import ParentStudentLinkingPage from "../pages/parent/ParentStudentLinkingPage";
import ParentReportCardsPage from "../pages/parent/ParentReportCardsPage";
import ParentAttendancePage from "../pages/parent/ParentAttendancePage";
import AnnouncementsWorkspacePage from "../pages/shared/AnnouncementsWorkspacePage";
import SchoolCalendarPage from "../pages/shared/SchoolCalendarPage";
import RoleSettingsPage from "../pages/shared/RoleSettingsPage";
import SchoolSwitchPage from "../pages/shared/SchoolSwitchPage";
import MembershipScopeGuard from "./MembershipScopeGuard";
import RoleGuard from "./RoleGuard";

export const parentRoutes = (
  <Route element={<RoleGuard allowedRoles={["PARENT"]} />}>
    <Route element={<DashboardShell role="parent" onboardingModalEnabled={false} />}>
      <Route path="/parent/schools" element={<SchoolSwitchPage role="parent" />} />
    </Route>

    <Route element={<MembershipScopeGuard role="parent" />}>
      <Route element={<DashboardShell role="parent" />}>
        <Route path="/parent/dashboard" element={<ParentDashboardPage />} />
        <Route path="/parent/student-linking" element={<ParentStudentLinkingPage />} />
        <Route path="/parent/report-cards" element={<ParentReportCardsPage />} />
        <Route path="/parent/attendance" element={<ParentAttendancePage />} />
        <Route path="/parent/calendar" element={<SchoolCalendarPage role="parent" />} />
        <Route path="/parent/results" element={<ParentResultsPage />} />
        <Route path="/parent/notices" element={<AnnouncementsWorkspacePage mode="parent" />} />
        <Route path="/parent/settings" element={<RoleSettingsPage role="parent" />} />
      </Route>
    </Route>
  </Route>
);
