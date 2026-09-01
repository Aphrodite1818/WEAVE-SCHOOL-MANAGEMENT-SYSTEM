import assert from "node:assert/strict";
import test from "node:test";

import {
  buildAcademicHubDirectory,
  filterAcademicHubDirectory,
} from "./academicHubDirectory.js";

test("academic hub directory keeps every supported entity in workflow order", () => {
  const rows = buildAcademicHubDirectory({});

  assert.equal(rows.length, 14);
  assert.deepEqual(rows.slice(0, 4).map((row) => row.key), [
    "sessions",
    "terms",
    "levels",
    "arm-labels",
  ]);
  assert.equal(rows.at(-1).key, "progression");
});

test("academic hub directory derives only backend-grounded live states", () => {
  const rows = buildAcademicHubDirectory({
    active_academic_session: "2026/2027",
    active_academic_term: "first_term",
    total_classes: 12,
    total_subjects: 18,
    result_rows_total: 320,
    result_rows_submitted: 7,
  });

  assert.equal(rows.find((row) => row.key === "sessions").state, "Open");
  assert.equal(rows.find((row) => row.key === "classes").scope, "12 classes");
  assert.equal(rows.find((row) => row.key === "results").state, "Needs review");
});

test("academic hub search matches descriptions and lifecycle text", () => {
  const rows = buildAcademicHubDirectory({}).map((row) => ({
    ...row,
    title: row.key,
    description: row.key === "curriculum" ? "Subjects taught at each level" : "",
  }));

  assert.deepEqual(filterAcademicHubDirectory(rows, "subjects taught").map((row) => row.key), ["curriculum"]);
  assert.ok(filterAcademicHubDirectory(rows, "archived").some((row) => row.key === "levels"));
});
