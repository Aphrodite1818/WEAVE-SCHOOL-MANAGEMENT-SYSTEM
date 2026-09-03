import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = async (path) => readFile(new URL(`../../${path}`, import.meta.url), "utf8");

test("student dashboard keeps Promise.all responses aligned", async () => {
  const source = await read("src/pages/student/StudentDashboardPage.jsx");
  const bundleStart = source.indexOf("const bundle = await getCachedDashboardBundle");
  const bundleEnd = source.indexOf("if (!mounted || controller.signal.aborted) return;", bundleStart);
  const bundle = source.slice(bundleStart, bundleEnd);

  assert.equal((bundle.match(/studentService\.getMyStudent/g) || []).length, 0);
  assert.equal((bundle.match(/studentService\.getMyParentLinks/g) || []).length, 1);
  assert.equal((bundle.match(/studentService\.getMyParentLinkRequests/g) || []).length, 1);
  assert.equal((bundle.match(/dashboardService\.getStudentAnalytics/g) || []).length, 1);
  assert.equal((bundle.match(/academicService\.listMyResults/g) || []).length, 1);
  assert.equal((bundle.match(/reportCardService\.listMyReportCards/g) || []).length, 1);
  assert.equal((bundle.match(/academicService\.listMySubjectCards/g) || []).length, 1);
});

test("term checkout resolves only an unambiguous eligible term", async () => {
  const source = await read("src/services/subscriptionService.js");
  assert.doesNotMatch(source, /TERM_ORDER/);
  assert.match(source, /currentTerms\.length === 1/);
  assert.match(source, /There is no open academic term to manage/);
  assert.match(source, /item\.is_current && item\.status === "open"/);
  assert.doesNotMatch(source, /\["open", "closing"\]/);
});

test("teacher assignment class selector uses the backend 500-class contract", async () => {
  const source = await read("src/features/academic-admin/TeacherAssignmentsWorkspace.jsx");
  assert.match(source, /getClasses\(\{ limit: 500, activeOnly: true \}\)/);
});

test("teacher assignment payload is curriculum-subject only", async () => {
  const source = await read("src/services/academicService.js");
  const curriculumService = await read("src/services/curriculumService.js");
  const workspace = await read("src/features/academic-admin/TeacherAssignmentsWorkspace.jsx");
  assert.match(source, /curriculum_subject_id: payload\.curriculum_subject_id/);
  assert.doesNotMatch(source, /level_subject_id/);
  assert.match(curriculumService, /getEligibleClasses/);
  assert.match(curriculumService, /createTeacherAssignmentsBulk/);
  assert.match(workspace, /class_ids: selectedClassIds/);
  assert.match(workspace, /curriculumService\.getEligibleClasses/);
});

test("normal and guided level creation share the institution-scoped levels workspace", async () => {
  const workflowPage = await read("src/pages/admin/AcademicWorkflowPage.jsx");
  const guideWorkspace = await read("src/features/guides/AdminGuideTaskWorkspace.jsx");
  const levelsWorkspace = await read("src/features/academic-admin/AcademicLevelsWorkspace.jsx");

  assert.match(workflowPage, /workflow === "levels"[\s\S]*<AcademicLevelsWorkspace/);
  assert.match(guideWorkspace, /kind === "levels".*<AcademicLevelsWorkspace/s);
  assert.match(levelsWorkspace, /academicLevelService\.getCategories\(\)/);
});

test("department client separates canonical pool from level availability", async () => {
  const source = await read("src/services/departmentService.js");
  const academicsSource = await read("src/services/academicsService.js");

  assert.match(source, /\/tenant-admin\/academics\/departments/);
  assert.match(source, /academic-levels\/\$\{levelId\}\/departments/);
  assert.match(source, /department_id: departmentId/);
  assert.match(source, /ACTIVATE_LEVEL_DEPARTMENT/);
  assert.doesNotMatch(academicsSource, /export const departmentService/);
});

test("class specialization writes only the level-department mapping identity", async () => {
  const service = await read("src/services/curriculumService.js");
  const workspace = await read("src/features/academic-admin/DepartmentsWorkspace.jsx");

  assert.match(service, /academic_level_department_id: academicLevelDepartmentId/);
  assert.doesNotMatch(service, /department_id: departmentId/);
  assert.match(workspace, /assignment\?\.academic_level_department_id/);
  assert.match(workspace, /departmentService\.getLevelDepartments/);
});

test("curriculum applicability uses active level-department mappings", async () => {
  const workspace = await read("src/features/academic-admin/CurriculumWorkspace.jsx");

  assert.match(workspace, /departmentService\.getLevelDepartments\(levelId, \{ activeOnly: true \}\)/);
  assert.match(workspace, /academic_level_department_ids: selectedDepartmentIds/);
  assert.doesNotMatch(workspace, /department_id:/);
});

test("department workflow exposes pool, availability and placements only", async () => {
  const source = await read("src/features/academic-admin/academicWorkflowConfig.js");
  const start = source.indexOf("departments: {");
  const end = source.indexOf("subjects: {", start);
  const departmentConfig = source.slice(start, end);

  assert.match(departmentConfig, /defaultTab: "pool"/);
  assert.match(departmentConfig, /id: "pool", label: "Department Pool"/);
  assert.match(departmentConfig, /id: "availability", label: "Level Availability"/);
  assert.match(departmentConfig, /id: "placements", label: "Class Placements"/);
  assert.doesNotMatch(departmentConfig, /id: "create"/);
  assert.doesNotMatch(departmentConfig, /id: "archived"/);
});
