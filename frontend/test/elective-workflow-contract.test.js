import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const read = (path) =>
  fs.readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

const curriculum = read("src/features/academic-admin/CurriculumWorkspace.jsx");
const studentPage = read("src/pages/student/StudentSubjectsPage.jsx");
const studentPanel = read("src/components/student/StudentElectiveSelectionPanel.jsx");

test("curriculum administration exposes elective group management", () => {
  assert.match(curriculum, /Manage Elective Groups/);
  assert.match(curriculum, /listElectiveGroups\(levelId\)/);
  assert.match(curriculum, /elective_group_id: elective \? addElectiveGroupId : null/);
  assert.match(curriculum, /elective && !addElectiveGroupId/);
  assert.match(curriculum, /Elective settings/);
});

test("student subjects page loads and refreshes authoritative elective choices", () => {
  assert.match(studentPage, /getMyElectiveWorkspace\(\)/);
  assert.match(studentPage, /updateMyElectiveSelection/);
  assert.match(studentPage, /listMySubjectCards\(\)/);
  assert.match(studentPage, /StudentElectiveSelectionPanel/);
});

test("student elective controls expose lock state and choice bounds", () => {
  assert.match(studentPanel, /group\.locked/);
  assert.match(studentPanel, /group\.minimum_choices/);
  assert.match(studentPanel, /group\.maximum_choices/);
  assert.match(studentPanel, /Save choices/);
});
