import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(
  new URL("../src/features/academic-admin/TeacherAssignmentsWorkspace.jsx", import.meta.url),
  "utf8",
);

test("teacher assignment creation is level-first instead of anchor-class-first", () => {
  assert.match(source, /label="Academic level"/);
  assert.match(source, /curriculumService\s*\.getCurriculum\(assignmentLevelId\)/);
  assert.doesNotMatch(source, /getResolvedClassSubjects\(form\.class_id/);
  assert.doesNotMatch(source, /Choose a class to find its eligible subjects/);
});

test("eligible classes are constrained to the selected academic level", () => {
  assert.match(source, /item\.academic_level_id === assignmentLevelId/);
  assert.match(source, /getEligibleClasses\(/);
  assert.match(source, /Select all eligible/);
  assert.doesNotMatch(source, /eligibleClassGroups/);
});

test("assignment cards consume canonical scheduled-current-ended status", () => {
  assert.match(source, /renderStatus=\{\(item\) => String\(item\.status/);
  assert.doesNotMatch(source, /viewingAssignment\.is_active/);
  assert.match(source, /item\.status\)\.toLowerCase\(\) === "current"/);
  assert.match(source, /item\.status\)\.toLowerCase\(\) === "scheduled"/);
});
