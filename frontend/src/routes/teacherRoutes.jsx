import { Navigate, Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import TeacherAttendancePage from "../pages/teacher/AttendancePage";
import TeacherDashboardPage from "../pages/teacher/TeacherDashboardPage";
import TeacherClassesPage from "../pages/teacher/MyClassesPage";
import TeacherResultsPage from "../pages/teacher/ResultsPage";
import TeacherStudentsPage from "../pages/teacher/StudentsPage";
import TeacherSubjectsPage from "../pages/teacher/SubjectsPage";
import AnnouncementsWorkspacePage from "../pages/shared/AnnouncementsWorkspacePage";
import RoleAnalyticsPage from "../pages/shared/RoleAnalyticsPage";
import SchoolCalendarPage from "../pages/shared/SchoolCalendarPage";
import RoleSettingsPage from "../pages/shared/RoleSettingsPage";
import SchoolSwitchPage from "../pages/shared/SchoolSwitchPage";
import StaticModulePage from "../pages/shared/StaticModulePage";
import MembershipScopeGuard from "./MembershipScopeGuard";
import RoleGuard from "./RoleGuard";

export const teacherRoutes = (
  <Route element={<RoleGuard allowedRoles={["TEACHER"]} />}>
    <Route element={<DashboardShell role="teacher" onboardingModalEnabled={false} />}>
      <Route path="/teacher/schools" element={<SchoolSwitchPage role="teacher" />} />
    </Route>

    <Route element={<MembershipScopeGuard role="teacher" />}>
      <Route element={<DashboardShell role="teacher" />}>
        <Route path="/teacher/dashboard" element={<TeacherDashboardPage />} />
        <Route path="/teacher/analytics" element={<RoleAnalyticsPage role="teacher" />} />
        <Route path="/teacher/classes" element={<TeacherClassesPage />} />
        <Route path="/teacher/students" element={<TeacherStudentsPage />} />
        <Route path="/teacher/subjects" element={<TeacherSubjectsPage />} />
        <Route path="/teacher/attendance" element={<TeacherAttendancePage />} />
        <Route path="/teacher/exams" element={<Navigate to="/teacher/score-entry" replace />} />
        <Route path="/teacher/results" element={<Navigate to="/teacher/score-entry" replace />} />
        <Route path="/teacher/score-entry" element={<TeacherResultsPage />} />
        <Route path="/teacher/assignments" element={<StaticModulePage role="teacher" title="Assignments" description="Create, review, and track classroom assignments." />} />
        <Route path="/teacher/calendar" element={<SchoolCalendarPage role="teacher" />} />
        <Route path="/teacher/timetable" element={<Navigate to="/teacher/calendar" replace />} />
        <Route path="/teacher/notices" element={<AnnouncementsWorkspacePage mode="teacher" variant="received-notices" />} />
        <Route path="/teacher/announcements" element={<AnnouncementsWorkspacePage mode="teacher" />} />
        <Route path="/teacher/settings" element={<RoleSettingsPage role="teacher" />} />
      </Route>
    </Route>
  </Route>
);
