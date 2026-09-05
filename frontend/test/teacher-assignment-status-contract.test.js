import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(
  new URL("../src/features/academic-admin/TeacherAssignmentsWorkspace.jsx", import.meta.url),
  "utf8",
);

test("teacher assignment requests use the canonical lifecycle statuses", () => {
  assert.doesNotMatch(source, /status:\s*["']active["']/);
  assert.match(source, /status:\s*["']current["']/);
  assert.match(source, /status:\s*["']scheduled["']/);
  assert.match(source, /value:\s*["']scheduled["'], label:\s*["']Scheduled["']/);
  assert.match(source, /value:\s*["']current["'], label:\s*["']Current["']/);
  assert.match(source, /value:\s*["']ended["'], label:\s*["']Ended["']/);
});

test("class subject availability protects both current and scheduled assignments", () => {
  assert.match(source, /const \[resolvedSubjects, currentResponse, scheduledResponse\]/);
  assert.match(source, /\.\.\.asItems\(currentResponse\)/);
  assert.match(source, /\.\.\.asItems\(scheduledResponse\)/);
  assert.match(source, /protectedAssignments/);
});
