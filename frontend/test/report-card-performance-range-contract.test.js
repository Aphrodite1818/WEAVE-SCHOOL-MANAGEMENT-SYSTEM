import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("report card comments are selected by performance range, including zero percent", async () => {
  const workspace = await read(
    "src/features/academic-admin/ReportCardsWorkspace.jsx",
  );

  assert.match(
    workspace,
    /value === null \|\| value === undefined \|\| value === ""/,
  );
  assert.match(
    workspace,
    /disabled=\{asNumber\(selectedStudent\?\.performance_percentage\) === null\}/,
  );
  assert.doesNotMatch(
    workspace,
    /disabled=\{!selectedStudent\?\.performance_percentage\}/,
  );
  assert.match(workspace, /minimum_score/);
  assert.match(workspace, /maximum_score/);
  assert.match(workspace, /performance-range default/);
  assert.doesNotMatch(workspace, /grading_scale_ids|default_grading_scale_ids/);
});

test("report readiness remains server paginated", async () => {
  const workspace = await read(
    "src/features/academic-admin/ReportCardsWorkspace.jsx",
  );
  const service = await read("src/services/reportCardService.js");

  assert.match(workspace, /READINESS_PAGE_SIZE = 50/);
  assert.match(workspace, /offset: readinessPage \* READINESS_PAGE_SIZE/);
  assert.match(workspace, /limit: READINESS_PAGE_SIZE/);
  assert.match(workspace, /search: debouncedReadinessQuery \|\| undefined/);
  assert.match(service, /getClassOverview/);
});
