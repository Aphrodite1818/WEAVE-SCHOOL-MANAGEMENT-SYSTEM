import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

// Existing coverage is owned by the eligible-class API; the workspace must not recreate it.
const source = fs.readFileSync(
  new URL("../src/features/academic-admin/TeacherAssignmentsWorkspace.jsx", import.meta.url),
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
  assert.match(source, /\? ["']current["']/);
});

test("assignment creation delegates existing coverage to the eligible-class contract", () => {
  // Keep this formatting-insensitive: the service chain may wrap across lines.
  assert.match(source, /curriculumService\s*\.\s*getEligibleClasses\s*\(/);
  assert.match(source, /already_assigned/);
  assert.match(source, /filter\(\(item\) => !item\.already_assigned\)/);
});
