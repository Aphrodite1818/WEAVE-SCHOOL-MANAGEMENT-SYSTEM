import assert from "node:assert/strict";
import test from "node:test";

import { filterStudentCommentRows } from "./filterStudentCommentRows.js";

const rows = [
  { student_name: "Juliet Okafor", admission_number: "DBSC26314653" },
  { student_name: "Grace Balogun", admission_number: "DBSC26310557" },
];

test("student comment search matches names without case sensitivity", () => {
  assert.deepEqual(filterStudentCommentRows(rows, "jULIET"), [rows[0]]);
});

test("student comment search matches admission numbers", () => {
  assert.deepEqual(filterStudentCommentRows(rows, "0557"), [rows[1]]);
});

test("blank student comment search preserves the complete roster", () => {
  assert.equal(filterStudentCommentRows(rows, "   "), rows);
});

