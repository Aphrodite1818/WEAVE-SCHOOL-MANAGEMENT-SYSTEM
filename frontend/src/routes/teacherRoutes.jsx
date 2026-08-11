/* eslint-disable react-refresh/only-export-components */

import { lazy } from "react";
import { Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import MembershipScopeGuard from "./MembershipScopeGuard";
import RoleGuard from "./RoleGuard";
import RuntimeFeatureRoute from "./RuntimeFeatureRoute";

const CommunicationInboxPage = lazy(() => import("../pages/shared/CommunicationInboxPage"));
const MessagesPage = lazy(() => import("../pages/shared/MessagesPage"));
const RoleAnalyticsPage = lazy(() => import("../pages/shared/RoleAnalyticsPage"));
const RoleGettingStartedPage = lazy(() => import("../pages/shared/RoleGettingStartedPage"));
const RoleSettingsPage = lazy(() => import("../pages/shared/RoleSettingsPage"));
const SchoolCalendarPage = lazy(() => import("../pages/shared/SchoolCalendarPage"));
const SchoolSwitchPage = lazy(() => import("../pages/shared/SchoolSwitchPage"));
const TeacherAttendancePage = lazy(() => import("../pages/teacher/AttendancePage"));
const TeacherClassesPage = lazy(() => import("../pages/teacher/MyClassesPage"));
const TeacherStudentsPage = lazy(() => import("../pages/teacher/StudentsPage"));
const TeacherSubjectsPage = lazy(() => import("../pages/teacher/SubjectsPage"));
const TeacherDashboardPage = lazy(() => import("../pages/teacher/TeacherDashboardPage"));

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
        <Route path="/teacher/calendar" element={<SchoolCalendarPage role="teacher" />} />
        <Route path="/teacher/inbox" element={<CommunicationInboxPage />} />
        <Route path="/teacher/messages" element={<RuntimeFeatureRoute feature="messaging" role="teacher"><MessagesPage /></RuntimeFeatureRoute>} />
        <Route path="/teacher/settings" element={<RoleSettingsPage role="teacher" />} />
      </Route>
    </Route>
  </Route>
);
