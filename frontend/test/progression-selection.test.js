import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("academic levels use explicit category and position with no configurable progression graph", async () => {
  const source = await read("src/features/academic-admin/AcademicLevelsWorkspace.jsx");
  for (const field of ["category", "position"]) {
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
  const guided = await read("src/features/guides/roleGuideConfig.js");
  assert.match(page, /ProgressionWorkspace/);
  assert.doesNotMatch(page, /student-choices/);
  assert.match(config, /title: "Automatic Progression"/);
  assert.doesNotMatch(config, /student-choices|progression_mode/);
  assert.match(progression, /Automatic level transitions/);
  assert.match(progression, /class, arm, and department never affect it/);
  assert.match(progression, /Graduate/);
  assert.match(guided, /Review progression order/);
  assert.match(guided, /Level ordering and terminal-level review/);
});

test("frontend services use level enrollment, canonical class placement, and staged closure contracts", async () => {
  const students = await read("src/services/studentService.js");
  const sessions = await read("src/services/academicService.js");
  const curriculumService = await read("src/services/curriculumService.js");
  const curriculum = await read("src/features/academic-admin/CurriculumWorkspace.jsx");
  const directory = await read("src/pages/admin/StudentDirectoryPage.jsx");
  assert.match(students, /academic_level_id/);
  assert.match(students, /unassigned_class/);
  assert.match(students, /class-placement/);
  assert.doesNotMatch(
    students,
    /batch-class-assignment|progression\/selection|progression\/placement/,
  );
  assert.match(sessions, /start-closing/);
  assert.match(curriculumService, /getResolvedClassSubjects/);
  assert.match(curriculumService, /classes\/\$\{classId\}\/terms\/\$\{termId\}\/department/);
  assert.match(curriculum, /academic_level_department_ids: selectedDepartmentIds/);
  assert.match(directory, /current_department/);
  assert.match(directory, /destination_department/);
  assert.doesNotMatch(directory, /student\??\.department_name/);
  assert.match(directory, /effective_date/);
  assert.match(directory, /academic_session_id/);
});

test("Academic Hub supports ordered level updates, departments, and backend-guarded level deletion", async () => {
  const source = await read("src/features/academic-admin/AcademicLevelsWorkspace.jsx");
  const config = await read("src/features/academic-admin/academicWorkflowConfig.js");
  assert.match(source, /Update level/);
  assert.match(source, /updateLevel = async/);
  assert.match(source, /academicLevelService\.updateLevel\(editingLevelId/);
  assert.match(source, /category:/);
  assert.match(source, /position:/);
  const departments = await read("src/features/academic-admin/DepartmentsWorkspace.jsx");
  assert.match(departments, /departmentService\.createDepartment/);
  assert.match(source, /Delete empty level/);
  assert.match(source, /removeLevelFromSetup/);
  assert.match(source, /ConfirmDialog/);
  assert.doesNotMatch(source, /TypedConfirmationDialog|DELETE_EMPTY_LEVEL|ACTIVATE_ACADEMIC_LEVEL/);
  assert.match(source, /max-h-\[34rem\].*overflow-y-auto/);
  assert.doesNotMatch(config, /id: ["']progression["']/);
});

test("Subjects by Level keeps separate assignment and lifecycle pages", async () => {
  const source = await read("src/features/academic-admin/CurriculumWorkspace.jsx");
  const config = await read("src/features/academic-admin/academicWorkflowConfig.js");
  assert.match(config, /curriculum: \{/);
  assert.match(config, /Curriculum Subjects/);
  assert.match(source, /Add subjects to curriculum/);
  assert.match(source, /Subject applicability/);
  assert.match(source, /curriculumService\.addSubject/);
  assert.match(source, /academic_level_department_ids/);
  assert.match(source, /academic_level_department_ids/);
  assert.match(source, /is_elective: elective/);
  assert.doesNotMatch(source, /is_core/);
});
