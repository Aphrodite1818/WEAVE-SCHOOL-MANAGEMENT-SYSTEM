import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import LandingPage from "../pages/public/LandingPage";
import LoginPage from "../pages/public/LoginPage";
import RegisterPage from "../pages/public/RegisterPage";
import OTPValidationPage from "../pages/public/otp_validationPage";
import InvitePage from "../pages/public/InvitePage";
import ForgotPasswordPage from "../pages/public/ForgotPasswordPage";
import AdminDashboardPage from "../pages/admin/AdminDashboardPage";
import CreateUserPage from "../pages/admin/CreateUserPage";
import TeachersPage from "../pages/admin/TeachersPage";
import StudentsPage from "../pages/admin/StudentsPage";
import ParentsPage from "../pages/admin/ParentsPage";
import ClassesPage from "../pages/admin/ClassesPage";
import SubjectsPage from "../pages/admin/SubjectsPage";
import AttendancePage from "../pages/admin/AttendancePage";
import ExamsPage from "../pages/admin/ExamsPage";
import ResultsPage from "../pages/admin/ResultsPage";
import AcademicPage from "../pages/admin/AcademicPage";
import FeesPage from "../pages/admin/FeesPage";
import PaymentsPage from "../pages/admin/PaymentsPage";
import TeacherDashboardPage from "../pages/teacher/TeacherDashboardPage";
import TeacherClassesPage from "../pages/teacher/MyClassesPage";
import TeacherStudentsPage from "../pages/teacher/StudentsPage";
import TeacherSubjectsPage from "../pages/teacher/SubjectsPage";
import TeacherAttendancePage from "../pages/teacher/AttendancePage";
import TeacherExamsPage from "../pages/teacher/ExamsPage";
import TeacherResultsPage from "../pages/teacher/ResultsPage";
import StudentChangePasswordPage from "../pages/student/StudentChangePasswordPage";
import StudentDashboardPage from "../pages/student/StudentDashboardPage";
import StudentSubjectsPage from "../pages/student/StudentSubjectsPage";
import StudentSubjectDetailsPage from "../pages/student/StudentSubjectDetailsPage";
import StudentParentLinkingPage from "../pages/student/StudentParentLinkingPage";
import StudentReportCardsPage from "../pages/student/StudentReportCardsPage";
import ParentDashboardPage from "../pages/parent/ParentDashboardPage";
import ParentStudentLinkingPage from "../pages/parent/ParentStudentLinkingPage";
import ParentResultsPage from "../pages/parent/ParentResultsPage";
import ParentReportCardsPage from "../pages/parent/ParentReportCardsPage";
import SuperadminDashboardPage from "../pages/superadmin/SuperadminDashboardPage";
import LegalPage from "../pages/shared/LegalPage";
import StaticModulePage from "../pages/shared/StaticModulePage";
import ProfileSettingsPage from "../pages/shared/ProfileSettingsPage";
import AnnouncementsWorkspacePage from "../pages/shared/AnnouncementsWorkspacePage";
import ProtectedRoute from "./ProtectedRoute";
import RoleGuard from "./RoleGuard";

function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-otp" element={<OTPValidationPage />} />
        <Route path="/invite" element={<InvitePage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/profile" element={<ProfileSettingsPage />} />
          <Route path="/legal" element={<LegalPage />} />

          <Route element={<RoleGuard allowedRoles={["ADMIN"]} />}>
            <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
            <Route path="/admin/create-user" element={<CreateUserPage />} />
            <Route path="/admin/teachers" element={<TeachersPage />} />
            <Route path="/admin/students" element={<StudentsPage />} />
            <Route path="/admin/parents" element={<ParentsPage />} />
            <Route path="/admin/classes" element={<ClassesPage />} />
            <Route path="/admin/subjects" element={<SubjectsPage />} />
            <Route path="/admin/attendance" element={<AttendancePage />} />
            <Route path="/admin/exams" element={<Navigate to="/admin/academic" replace />} />
            <Route path="/admin/results" element={<Navigate to="/admin/academic" replace />} />
            <Route path="/admin/academic" element={<AcademicPage />} />
            <Route path="/admin/fees" element={<FeesPage />} />
            <Route path="/admin/payments" element={<PaymentsPage />} />
            <Route path="/admin/timetable" element={<StaticModulePage role="admin" title="Timetable" description="Professional schedule grid and class timetable planning." type="timetable" />} />
            <Route path="/admin/announcements" element={<AnnouncementsWorkspacePage mode="tenant-admin" />} />
            <Route path="/admin/messages" element={<AnnouncementsWorkspacePage mode="tenant-admin" variant="messages" />} />
            <Route path="/admin/reports" element={<StaticModulePage role="admin" title="Reports" description="Operational reports will appear here when backend reporting endpoints are available." type="settings" />} />
            <Route path="/admin/settings" element={<StaticModulePage role="admin" title="Settings" description="School profile, security, users, and account configuration." type="settings" />} />
          </Route>

          <Route element={<RoleGuard allowedRoles={["TEACHER"]} />}>
            <Route path="/teacher/dashboard" element={<TeacherDashboardPage />} />
            <Route path="/teacher/classes" element={<TeacherClassesPage />} />
            <Route path="/teacher/students" element={<TeacherStudentsPage />} />
            <Route path="/teacher/subjects" element={<TeacherSubjectsPage />} />
            <Route path="/teacher/attendance" element={<TeacherAttendancePage />} />
            <Route path="/teacher/exams" element={<Navigate to="/teacher/results" replace />} />
            <Route path="/teacher/results" element={<TeacherResultsPage />} />
            <Route path="/teacher/assignments" element={<StaticModulePage role="teacher" title="Assignments" description="Create, review, and track classroom assignments." />} />
            <Route path="/teacher/timetable" element={<StaticModulePage role="teacher" title="Timetable" description="Daily teaching schedule and class periods." type="timetable" />} />
            <Route path="/teacher/notices" element={<AnnouncementsWorkspacePage mode="teacher" variant="received-notices" />} />
            <Route path="/teacher/announcements" element={<AnnouncementsWorkspacePage mode="teacher" />} />
          </Route>

          <Route element={<RoleGuard allowedRoles={["STUDENT"]} />}>
            <Route path="/student/change-password" element={<StudentChangePasswordPage />} />
            <Route path="/student/dashboard" element={<StudentDashboardPage />} />
            <Route path="/student/subjects" element={<StudentSubjectsPage />} />
            <Route path="/student/subjects/:subjectResultId" element={<StudentSubjectDetailsPage />} />
            <Route path="/student/parent-linking" element={<StudentParentLinkingPage />} />
            <Route path="/student/report-cards" element={<StudentReportCardsPage />} />
            <Route path="/student/timetable" element={<StaticModulePage role="student" title="Timetable" description="Your class schedule and upcoming periods." type="timetable" />} />
            <Route path="/student/assignments" element={<StaticModulePage role="student" title="Assignments" description="Track assigned work and due dates." />} />
            <Route path="/student/results" element={<StaticModulePage role="student" title="Results" description="Review academic performance and report summaries." />} />
            <Route path="/student/notices" element={<AnnouncementsWorkspacePage mode="student" />} />
          </Route>

          <Route element={<RoleGuard allowedRoles={["PARENT"]} />}>
            <Route path="/parent/dashboard" element={<ParentDashboardPage />} />
            <Route path="/parent/student-linking" element={<ParentStudentLinkingPage />} />
            <Route path="/parent/report-cards" element={<ParentReportCardsPage />} />
            <Route path="/parent/attendance" element={<StaticModulePage role="parent" title="Attendance" description="Review attendance summaries for your children." />} />
            <Route path="/parent/results" element={<ParentResultsPage />} />
            <Route path="/parent/notices" element={<AnnouncementsWorkspacePage mode="parent" />} />
            <Route path="/parent/fees" element={<StaticModulePage role="parent" title="Fees" description="Fee statements, payment status, and due dates." />} />
          </Route>

          <Route element={<RoleGuard allowedRoles={["SUPERADMIN"]} />}>
            <Route path="/superadmin/dashboard" element={<SuperadminDashboardPage />} />
            <Route path="/superadmin/announcements" element={<AnnouncementsWorkspacePage mode="superadmin" />} />
            <Route path="/superadmin/verification" element={<StaticModulePage role="superadmin" title="Verification" description="Tenant verification activity and approval workflow." type="settings" />} />
            <Route path="/superadmin/activity" element={<StaticModulePage role="superadmin" title="Platform Activity" description="Recent registrations, verification events, and system statistics." type="ai" />} />
            <Route path="/superadmin/settings" element={<StaticModulePage role="superadmin" title="Platform Settings" description="Platform-wide configuration and administrator controls." type="settings" />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default AppRoutes;
