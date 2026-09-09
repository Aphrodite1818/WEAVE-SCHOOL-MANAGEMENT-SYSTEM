import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(
  new URL("../src/pages/admin/StudentDirectoryPage.jsx", import.meta.url),
  "utf8",
);
const serviceSource = fs.readFileSync(
  new URL("../src/services/studentService.js", import.meta.url),
  "utf8",
);

test("terminal student actions are presented as immediate without schedulable dates", () => {
  assert.match(source, /withdraw:[\s\S]*immediate: true/);
  assert.match(source, /expel:[\s\S]*immediate: true/);
  assert.match(source, /graduate:[\s\S]*immediate: true/);
  assert.match(source, /Effective immediately/);
  assert.doesNotMatch(source, /usesGraduationDate/);
  assert.doesNotMatch(source, /graduation_date: form\.graduation_date/);
});

test("future placement and formal-return controls remain date enabled", () => {
  assert.match(source, /returnFlow: true/);
  assert.match(source, /Future return dates are allowed/);
  assert.doesNotMatch(source, /max=\{localDateInputValue\(\)\}/);
});

test("upcoming enrollment is distinct and can be edited or cancelled", () => {
  assert.match(source, /Upcoming enrollment/);
  assert.match(source, /Edit upcoming/);
  assert.match(source, /Cancel upcoming/);
  assert.match(serviceSource, /updateUpcomingEnrollment/);
  assert.match(serviceSource, /cancelUpcomingEnrollment/);
});
