import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const departmentsWorkspace = fs.readFileSync(
  new URL("../src/features/academic-admin/DepartmentsWorkspace.jsx", import.meta.url),
  "utf8",
);
const curriculumWorkspace = fs.readFileSync(
  new URL("../src/features/academic-admin/CurriculumWorkspace.jsx", import.meta.url),
  "utf8",
);

test("department availability does not own curriculum subject applicability", () => {
  assert.doesNotMatch(departmentsWorkspace, /Subjects using this level's departments/);
  assert.doesNotMatch(departmentsWorkspace, /curriculumService/);
  assert.doesNotMatch(departmentsWorkspace, /toggleSubjectDepartment/);

  assert.match(curriculumWorkspace, /title="Subject applicability"/);
  assert.match(curriculumWorkspace, /curriculumService\.updateSubject/);
  assert.match(curriculumWorkspace, /academic_level_department_ids/);
});
