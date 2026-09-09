import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

// Existing coverage is owned by the eligible-class API; the workspace must not recreate it.
const source = fs.readFileSync(
  new URL("../src/features/academic-admin/TeacherAssignmentsWorkspace.jsx", import.meta.url),
  "utf8",
);
const serviceSource = fs.readFileSync(
  new URL("../src/services/academicService.js", import.meta.url),
  "utf8",
);

test("teacher assignment requests use the canonical lifecycle statuses", () => {
  assert.doesNotMatch(source, /status:\s*["']active["']/);
  assert.match(source, /value:\s*["']scheduled["'], label:\s*["']Scheduled["']/);
  assert.match(source, /value:\s*["']current["'], label:\s*["']Current["']/);
  assert.match(source, /value:\s*["']ended["'], label:\s*["']Ended["']/);

  // Reassign/end are lifecycle actions on CURRENT records, not navigation tabs.
  assert.match(source, /if \(status === ["']current["']\)/);
  assert.match(source, /open=\{Boolean\(reassigning\)\}/);
  assert.match(source, /open=\{Boolean\(ending\)\}/);
  assert.match(source, /status: filters\.status \|\| undefined/);
});

test("assignment creation delegates existing coverage to the eligible-class contract", () => {
  // Keep this formatting-insensitive: the service chain may wrap across lines.
  assert.match(source, /curriculumService\s*\.\s*getEligibleClasses\s*\(/);
  assert.match(source, /already_assigned/);
  assert.match(source, /filter\(\(item\) => !item\.already_assigned\)/);
});

test("scheduled assignments and takeovers use dedicated lifecycle controls", () => {
  assert.match(source, /item\.has_scheduled_takeover/);
  assert.match(source, /Manage handover/);
  assert.match(source, /HANDOVER SCHEDULED/);
  assert.match(source, /if \(status === ["']scheduled["']\)/);
  assert.match(source, /Edit schedule/);
  assert.match(source, /Cancel schedule/);
  assert.match(source, /updateScheduledTeacherAssignment/);
  assert.match(source, /cancelScheduledTeacherAssignment/);
  assert.doesNotMatch(source, /Delete unused/);
});

test("early ending warns that the planned takeover is cancelled", () => {
  assert.match(
    source,
    /Ending this assignment early will also cancel the planned takeover/,
  );
  assert.match(source, /will have no assigned teacher/);
});

test("filter requests cannot be overwritten by stale assignment responses", () => {
  assert.match(source, /assignmentRequestGeneration\s*=\s*useRef\(0\)/);
  assert.match(source, /requestGeneration\s*!==\s*assignmentRequestGeneration\.current/);
  assert.match(source, /loadAssignments\(\{ signal: controller\.signal \}\)/);
  assert.match(source, /return \(\) => controller\.abort\(\)/);
  assert.match(serviceSource, /listTeacherAssignments:\s*\(params, options\)/);
  assert.match(serviceSource, /queryString\(params\)[\s\S]*options/);
});
