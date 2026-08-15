import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("academic levels use explicit category and position with no configurable progression graph", async () => {
  const source = await read("src/features/academic-admin/ClassStructureWorkspace.jsx");
  for (const field of ["category", "position", "specialization_required_from_term_position"]) {
    assert.match(source, new RegExp(field));
  }
  assert.doesNotMatch(source, /progression_mode|next_level_id|is_terminal|Allowed destinations/);
});

test("student, parent, and teacher dashboards no longer expose progression choices", async () => {
  const student = await read("src/pages/student/StudentDashboardPage.jsx");
  const parent = await read("src/pages/parent/ParentDashboardPage.jsx");
  const teacher = await read("src/pages/teacher/TeacherDashboardPage.jsx");
  for (const source of [student, parent, teacher]) {
    assert.doesNotMatch(source, /submitProgressionSelection|getChildProgression|getMyProgressions/);
    assert.doesNotMatch(source, /Choose your next academic level|awaiting_class_placement/);
  }
});

test("Academic Hub replaces student-choice placement with read-only level transitions", async () => {
  const page = await read("src/pages/admin/AcademicWorkflowPage.jsx");
  const config = await read("src/features/academic-admin/academicWorkflowConfig.js");
  const progression = await read("src/features/academic-admin/ProgressionWorkspace.jsx");
  const guided = await read("src/pages/admin/AdminGettingStartedPage.jsx");
  assert.match(page, /ProgressionWorkspace/);
  assert.doesNotMatch(page, /student-choices/);
  assert.match(config, /title: "Automatic Progression"/);
  assert.doesNotMatch(config, /student-choices|progression_mode/);
  assert.match(progression, /Automatic level transitions/);
  assert.match(progression, /class, arm, and department never affect progression/);
  assert.match(progression, /Graduate/);
  assert.match(guided, /Automatic level progression/);
  assert.match(guided, /Category and position define progression/);
});

test("frontend services use level enrollment, batch class assignment, and staged closure contracts", async () => {
  const students = await read("src/services/studentService.js");
  const sessions = await read("src/services/academicService.js");
  const directory = await read("src/pages/admin/StudentDirectoryPage.jsx");
  assert.match(students, /academic_level_id/);
  assert.match(students, /unassigned_class/);
  assert.match(students, /batch-class-assignment/);
  assert.doesNotMatch(students, /progression\/selection|progression\/placement/);
  assert.match(sessions, /start-closing/);
  assert.match(sessions, /level-subjects\/\$\{levelSubjectId\}\/offerings/);
  assert.match(sessions, /department-assignments/);
  assert.match(directory, /Department specialization/);
  assert.match(directory, /effective_from_term_id/);
});

test("Academic Hub supports ordered level updates, departments, and guarded level deletion", async () => {
  const source = await read("src/features/academic-admin/ClassStructureWorkspace.jsx");
  const config = await read("src/features/academic-admin/academicWorkflowConfig.js");
  assert.match(source, /Update level/);
  assert.match(source, /updateLevel\(editingLevelId/);
  assert.match(source, /category:/);
  assert.match(source, /position:/);
  assert.match(source, /departmentService\.createDepartment/);
  assert.match(source, /Delete empty level/);
  assert.match(source, /DELETE_EMPTY_LEVEL/);
  assert.match(source, /removeLevelFromSetup/);
  assert.match(source, /max-h-\[34rem\].*overflow-y-auto/);
  assert.doesNotMatch(config, /id: ["']progression["']/);
});

test("Subjects by Level keeps separate assignment and lifecycle pages", async () => {
  const source = await read("src/features/academic-admin/ClassStructureWorkspace.jsx");
  const config = await read("src/features/academic-admin/academicWorkflowConfig.js");
  const start = config.indexOf('"level-subjects": {');
  const end = config.indexOf("  assignments:", start);
  const levelSubjectConfig = config.slice(start, end);
  for (const tab of ["overview", "assign", "offerings", "active", "inactive", "archived"]) {
    assert.match(levelSubjectConfig, new RegExp(`id: ["']${tab}["']`));
  }
  assert.match(source, /activeTab === "assign"/);
  assert.match(source, /filteredLevelSubjects/);
  assert.match(source, /activeTab !== "overview"/);
  assert.match(source, /activeTab === "offerings"/);
  assert.match(source, /createSubjectOffering/);
  assert.match(source, /department_id: offeringForm\.department_id \|\| null/);
  assert.match(source, /is_elective: offeringForm\.is_elective/);
  assert.doesNotMatch(source, /is_core/);
});
