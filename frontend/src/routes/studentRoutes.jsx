import { Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import StudentChangePasswordPage from "../pages/student/StudentChangePasswordPage";
import StudentDashboardPage from "../pages/student/StudentDashboardPage";
import StudentParentLinkingPage from "../pages/student/StudentParentLinkingPage";
import StudentReportCardsPage from "../pages/student/StudentReportCardsPage";
import StudentSubjectDetailsPage from "../pages/student/StudentSubjectDetailsPage";
import StudentSubjectsPage from "../pages/student/StudentSubjectsPage";
import AnnouncementsWorkspacePage from "../pages/shared/AnnouncementsWorkspacePage";
import RoleAnalyticsPage from "../pages/shared/RoleAnalyticsPage";
import SchoolCalendarPage from "../pages/shared/SchoolCalendarPage";
import RoleSettingsPage from "../pages/shared/RoleSettingsPage";
import StaticModulePage from "../pages/shared/StaticModulePage";
import RoleGuard from "./RoleGuard";

export const studentRoutes = (
  <Route element={<RoleGuard allowedRoles={["STUDENT"]} />}>
    <Route element={<DashboardShell role="student" onboardingModalEnabled={false} />}>
      <Route path="/student/change-password" element={<StudentChangePasswordPage />} />
    </Route>
    <Route element={<DashboardShell role="student" />}>
      <Route path="/student/dashboard" element={<StudentDashboardPage />} />
      <Route path="/student/analytics" element={<RoleAnalyticsPage role="student" />} />
      <Route path="/student/subjects" element={<StudentSubjectsPage />} />
      <Route path="/student/subjects/:subjectResultId" element={<StudentSubjectDetailsPage />} />
      <Route path="/student/parent-linking" element={<StudentParentLinkingPage />} />
      <Route path="/student/report-cards" element={<StudentReportCardsPage />} />
      <Route path="/student/calendar" element={<SchoolCalendarPage role="student" />} />
      <Route path="/student/timetable" element={<SchoolCalendarPage role="student" />} />
      <Route path="/student/assignments" element={<StaticModulePage role="student" title="Assignments" description="Track assigned work and due dates." />} />
      <Route path="/student/results" element={<StaticModulePage role="student" title="Results" description="Review academic performance and report summaries." />} />
      <Route path="/student/notices" element={<AnnouncementsWorkspacePage mode="student" />} />
      <Route path="/student/settings" element={<RoleSettingsPage role="student" />} />
    </Route>
  </Route>
);
