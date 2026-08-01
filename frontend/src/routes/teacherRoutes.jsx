import { Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import CommunicationInboxPage from "../pages/shared/CommunicationInboxPage";
import MessagesPage from "../pages/shared/MessagesPage";
import RoleAnalyticsPage from "../pages/shared/RoleAnalyticsPage";
import RoleGettingStartedPage from "../pages/shared/RoleGettingStartedPage";
import RoleSettingsPage from "../pages/shared/RoleSettingsPage";
import SchoolCalendarPage from "../pages/shared/SchoolCalendarPage";
import SchoolSwitchPage from "../pages/shared/SchoolSwitchPage";
import TeacherAttendancePage from "../pages/teacher/AttendancePage";
import TeacherClassesPage from "../pages/teacher/MyClassesPage";
import TeacherResultsPage from "../pages/teacher/ResultsPage";
import TeacherStudentsPage from "../pages/teacher/StudentsPage";
import TeacherSubjectsPage from "../pages/teacher/SubjectsPage";
import TeacherDashboardPage from "../pages/teacher/TeacherDashboardPage";
import MembershipScopeGuard from "./MembershipScopeGuard";
import RoleGuard from "./RoleGuard";
import RuntimeFeatureRoute from "./RuntimeFeatureRoute";

export const teacherRoutes = (
  <Route element={<RoleGuard allowedRoles={["TEACHER"]} />}>
    <Route element={<DashboardShell role="teacher" onboardingModalEnabled={false} />}>
      <Route path="/teacher/schools" element={<SchoolSwitchPage role="teacher" />} />
    </Route>

    <Route element={<MembershipScopeGuard role="teacher" />}>
      <Route element={<DashboardShell role="teacher" />}>
        <Route path="/teacher/dashboard" element={<TeacherDashboardPage />} />
        <Route path="/teacher/getting-started" element={<RoleGettingStartedPage role="teacher" />} />
        <Route path="/teacher/analytics" element={<RoleAnalyticsPage role="teacher" />} />
        <Route path="/teacher/classes" element={<TeacherClassesPage />} />
        <Route path="/teacher/students" element={<TeacherStudentsPage />} />
        <Route path="/teacher/subjects" element={<TeacherSubjectsPage />} />
        <Route path="/teacher/attendance" element={<RuntimeFeatureRoute feature="attendance" role="teacher"><TeacherAttendancePage /></RuntimeFeatureRoute>} />
        <Route path="/teacher/score-entry" element={<TeacherResultsPage />} />
        <Route path="/teacher/calendar" element={<SchoolCalendarPage role="teacher" />} />
        <Route path="/teacher/inbox" element={<CommunicationInboxPage />} />
        <Route path="/teacher/messages" element={<RuntimeFeatureRoute feature="messaging" role="teacher"><MessagesPage /></RuntimeFeatureRoute>} />
        <Route path="/teacher/settings" element={<RoleSettingsPage role="teacher" />} />
      </Route>
    </Route>
  </Route>
);
