import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("analytics views stay backed by existing role metrics endpoints", async () => {
  const analyticsPage = await read("src/pages/shared/RoleAnalyticsPage.jsx");
  const dashboardService = await read("src/services/dashboard.service.js");

  for (const role of ["admin", "teacher", "student", "parent"]) {
    assert.match(analyticsPage, new RegExp(`\\b${role}: \\{`));
  }

  assert.match(dashboardService, /\/metrics\/tenant-admin\/dashboard/);
  assert.match(dashboardService, /\/metrics\/teacher\/dashboard/);
  assert.match(dashboardService, /\/metrics\/student\/dashboard/);
  assert.match(dashboardService, /\/metrics\/parent\/dashboard/);
  assert.doesNotMatch(analyticsPage, /Apply filters|All Years|All Subjects|All Classes/);
});

test("parent analytics is discoverable without inventing a backend route", async () => {
  const routes = await read("src/routes/parentRoutes.jsx");
  const navigation = await read("src/components/layout/navConfig.js");

  assert.match(routes, /path="\/parent\/analytics"[^>]*RoleAnalyticsPage role="parent"/);
  assert.match(navigation, /Family Insights[^\n]*\/parent\/analytics/);
});

test("actor dashboard metrics collapse to one column on narrow phones", async () => {
  const styles = await read("src/styles/mobileDashboard.css");
  const dashboards = await Promise.all([
    read("src/pages/admin/AdminDashboardPage.jsx"),
    read("src/pages/teacher/TeacherDashboardPage.jsx"),
    read("src/pages/student/StudentDashboardPage.jsx"),
    read("src/pages/parent/ParentDashboardPage.jsx"),
    read("src/pages/superadmin/SuperadminDashboardPage.jsx"),
  ]);

  assert.match(styles, /#dashboard-content \.dashboard-kpi-grid \{\s*grid-template-columns: minmax\(0, 1fr\)/);
  assert.match(styles, /@media \(min-width: 430px\)[\s\S]*repeat\(2, minmax\(0, 1fr\)\)/);
  dashboards.forEach((source) => assert.match(source, /dashboard-kpi-grid dashboard-kpi-grid-four/));
});
