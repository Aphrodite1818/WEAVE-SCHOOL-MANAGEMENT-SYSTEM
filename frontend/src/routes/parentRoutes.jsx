import { Route } from "react-router-dom";

import { DashboardShell } from "../components/layout/DashboardLayout";
import ParentDashboardPage from "../pages/parent/ParentDashboardPage";
import ParentResultsPage from "../pages/parent/ParentResultsPage";
import ParentStudentLinkingPage from "../pages/parent/ParentStudentLinkingPage";
import ParentReportCardsPage from "../pages/parent/ParentReportCardsPage";
import AnnouncementsWorkspacePage from "../pages/shared/AnnouncementsWorkspacePage";
import StaticModulePage from "../pages/shared/StaticModulePage";
import RoleGuard from "./RoleGuard";

export const parentRoutes = (
  <Route element={<RoleGuard allowedRoles={["PARENT"]} />}>
    <Route element={<DashboardShell role="parent" />}>
      <Route path="/parent/dashboard" element={<ParentDashboardPage />} />
      <Route path="/parent/student-linking" element={<ParentStudentLinkingPage />} />
      <Route path="/parent/report-cards" element={<ParentReportCardsPage />} />
      <Route path="/parent/attendance" element={<StaticModulePage role="parent" title="Attendance" description="Review attendance summaries for your children." />} />
      <Route path="/parent/results" element={<ParentResultsPage />} />
      <Route path="/parent/notices" element={<AnnouncementsWorkspacePage mode="parent" />} />
      <Route path="/parent/fees" element={<StaticModulePage role="parent" title="Fees" description="Fee statements, payment status, and due dates." />} />
    </Route>
  </Route>
);
