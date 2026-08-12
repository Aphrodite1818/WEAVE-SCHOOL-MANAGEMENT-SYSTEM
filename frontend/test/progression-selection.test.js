import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("academic progression configuration exposes all three explicit modes and target types", async () => {
  const source = await read("src/features/academic-admin/ClassStructureWorkspace.jsx");
  for (const value of ["direct", "student_selection", "terminal", "level", "classroom"]) {
    assert.match(source, new RegExp(`value: ["']${value}["']`));
  }
  assert.match(source, /Allowed destinations/);
  assert.doesNotMatch(source, /is_terminal/);
});

test("student progression UI supports immediate selection without approval language", async () => {
  const source = await read("src/pages/student/StudentDashboardPage.jsx");
  assert.match(source, /Choose your next academic level\./);
  assert.match(source, /Choose your next class\./);
  assert.match(source, /Your class placement is being finalized\./);
  assert.match(source, /submitProgressionSelection/);
  assert.doesNotMatch(source, /awaiting admin approval/i);
  assert.doesNotMatch(source, /approve|reject/i);
});

test("admin outcomes provide class placement and no selection approval action", async () => {
  const source = await read("src/features/academic-admin/ProgressionWorkspace.jsx");
  assert.match(source, /awaiting_class_placement/);
  assert.match(source, /placeProgressionStudent/);
  assert.match(source, /Assign class/);
  assert.doesNotMatch(source, /Approve selection|Reject selection/i);
});

test("frontend services use the canonical progression and staged closure contracts", async () => {
  const academics = await read("src/services/academicsService.js");
  const students = await read("src/services/studentService.js");
  const sessions = await read("src/services/academicService.js");
  assert.match(academics, /selection_target_type/);
  assert.match(academics, /target_level_ids/);
  assert.match(academics, /target_classroom_ids/);
  assert.match(students, /progression\/selection/);
  assert.match(students, /progression\/placement/);
  assert.match(sessions, /start-closing/);
  assert.doesNotMatch(sessions, /close-and-progress/);
});

test("guided setup and related actor dashboards expose progression state", async () => {
  const guided = await read("src/pages/admin/AdminGettingStartedPage.jsx");
  const parent = await read("src/pages/parent/ParentDashboardPage.jsx");
  const teacher = await read("src/pages/teacher/TeacherDashboardPage.jsx");
  assert.match(guided, /Progression mode/);
  assert.match(guided, /Allowed destinations/);
  assert.match(guided, /student_selection/);
  assert.match(parent, /getChildProgression/);
  assert.match(parent, /Progression choice needed/);
  assert.match(teacher, /getMyProgressions/);
  assert.match(teacher, /Student progression updates/);
});

test("Academic Hub supports level updates and guarded deletion of levels without arms", async () => {
  const source = await read("src/features/academic-admin/ClassStructureWorkspace.jsx");
  const config = await read("src/features/academic-admin/academicWorkflowConfig.js");
  assert.match(source, /Update level/);
  assert.match(source, /updateLevel\(editingLevelId/);
  assert.match(source, /armCount === 0/);
  assert.match(source, /Delete empty level/);
  assert.match(source, /DELETE_EMPTY_LEVEL/);
  assert.match(source, /removeLevelFromSetup/);
  assert.match(source, /max-h-\[34rem\].*overflow-y-auto/);
  assert.match(source, /overflow-y-auto.*sm:grid-cols-2/);
  assert.match(source, /flex-col items-start.*sm:flex-row/);
  assert.match(source, /w-full sm:w-auto/);
  assert.match(source, /armCount.*arm/);
  assert.match(source, /showSuccess\("Level progression updated\."\);\s*setSelectedLevelId\(""\)/);
  assert.match(source, /title="Configure level progression"/);
  assert.match(source, /placement="center"/);
  for (const tab of ["overview", "create", "manage", "progression"]) {
    assert.match(config, new RegExp(`id: ["']${tab}["']`));
  }
});
