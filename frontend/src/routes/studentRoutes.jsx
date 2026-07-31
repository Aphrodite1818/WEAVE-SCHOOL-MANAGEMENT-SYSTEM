import { Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import StudentChangePasswordPage from "../pages/student/StudentChangePasswordPage";
import StudentDashboardPage from "../pages/student/StudentDashboardPage";
import StudentParentLinkingPage from "../pages/student/StudentParentLinkingPage";
import StudentReportCardsPage from "../pages/student/StudentReportCardsPage";
import StudentAttendancePage from "../pages/student/StudentAttendancePage";
import StudentSubjectDetailsPage from "../pages/student/StudentSubjectDetailsPage";
import StudentSubjectsPage from "../pages/student/StudentSubjectsPage";
import CommunicationInboxPage from "../pages/shared/CommunicationInboxPage";
import MessagesPage from "../pages/shared/MessagesPage";
import RoleAnalyticsPage from "../pages/shared/RoleAnalyticsPage";
import SchoolCalendarPage from "../pages/shared/SchoolCalendarPage";
import RoleSettingsPage from "../pages/shared/RoleSettingsPage";
import RoleGuard from "./RoleGuard";
import RuntimeFeatureRoute from "./RuntimeFeatureRoute";

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
      <Route path="/student/attendance" element={<RuntimeFeatureRoute feature="attendance" role="student"><StudentAttendancePage /></RuntimeFeatureRoute>} />
      <Route path="/student/calendar" element={<SchoolCalendarPage role="student" />} />
      <Route path="/student/inbox" element={<CommunicationInboxPage />} />
      <Route path="/student/messages" element={<RuntimeFeatureRoute feature="messaging" role="student"><MessagesPage /></RuntimeFeatureRoute>} />
      <Route path="/student/settings" element={<RoleSettingsPage role="student" />} />
    </Route>
  </Route>
);
