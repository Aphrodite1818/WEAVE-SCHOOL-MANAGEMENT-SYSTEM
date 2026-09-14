import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { curriculumCopyPreview, curriculumCopySources } from "./curriculumCopy.js";

test("copy sources exclude the destination, other categories and inactive levels", () => {
  const target = { id: "p1", category: "PRIMARY", status: "active" };
  const same = { id: "p2", category: "PRIMARY", status: "active" };
  assert.deepEqual(curriculumCopySources([target, same,
    { id: "s1", category: "JUNIOR_SECONDARY", status: "active" },
    { id: "p3", category: "PRIMARY", status: "inactive" }], target), [same]);
  assert.deepEqual(curriculumCopySources([same], null), []);
});

test("preview preserves existing inactive memberships and flags missing department identity", () => {
  const source = [
    { subject_id: "math", is_active: true },
    { subject_id: "science", is_active: true, is_elective: true,
      departments: [{ department_id: "science-dept", department_name: "Science", academic_level_department_id: "source-link" }] },
    { subject_id: "history", is_active: false },
  ];
  const target = [{ subject_id: "math", is_active: false }];
  const preview = curriculumCopyPreview(source, target, []);
  assert.equal(preview.existingCount, 1);
  assert.deepEqual(preview.missing, [source[1]]);
  assert.deepEqual(preview.unavailableDepartments, ["Science"]);
  assert.deepEqual(curriculumCopyPreview(source, target,
    [{ department_id: "science-dept", id: "target-link" }]).unavailableDepartments, []);
});

test("copy form loads an isolated preview and submits through the dedicated backend operation", () => {
  const panel = readFileSync(new URL("./CurriculumCopyPanel.jsx", import.meta.url), "utf8");
  const workspace = readFileSync(new URL("./CurriculumWorkspace.jsx", import.meta.url), "utf8");
  const service = readFileSync(new URL("../../services/curriculumService.js", import.meta.url), "utf8");
  assert.match(panel, /if \(!cancelled\) setSource\(data\)/);
  assert.match(panel, /preview\.unavailableDepartments\.length/);
  assert.match(
    workspace,
    /curriculumService\.copyCurriculum\(\s*levelId,\s*sourceLevelId,?\s*\)/,
  );
  assert.match(workspace, /<CurriculumCopyPanel\s+key=\{levelId\}/);
  assert.match(service, /curriculum\/copy/);
  assert.match(service, /source_academic_level_id: sourceLevelId/);
});
