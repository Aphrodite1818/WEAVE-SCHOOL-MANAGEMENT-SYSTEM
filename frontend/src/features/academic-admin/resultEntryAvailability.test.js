import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  assignmentsAvailableForEntry,
  componentScoresForAssignment,
} from "./resultEntryAvailability.js";

const assignments = [
  { id: "math-assignment", class_id: "class-a", curriculum_subject_id: "math" },
  { id: "english-assignment", class_id: "class-a", curriculum_subject_id: "english" },
  { id: "science-assignment", class_id: "class-b", curriculum_subject_id: "science" },
];

test("result creation hides fully scored subjects and keeps partial subjects", () => {
  const results = [
    {
      curriculum_subject_id: "math",
      components: [
        { assessment_component_id: "ca-1", score: "15" },
        { assessment_component_id: "ca-2", score: "20" },
        { assessment_component_id: "exam", score: "55" },
      ],
    },
    {
      curriculum_subject_id: "english",
      components: [
        { assessment_component_id: "ca-1", score: "12" },
        { assessment_component_id: "ca-2", score: "18" },
        { assessment_component_id: "exam", score: null },
      ],
    },
  ];

  assert.deepEqual(
    assignmentsAvailableForEntry(assignments, results, "class-a").map((item) => item.id),
    ["english-assignment"],
  );
  assert.deepEqual(componentScoresForAssignment(results, assignments[1]), {
    "ca-1": "12",
    "ca-2": "18",
    exam: "",
  });
});

test("result creation keeps subjects with no result yet", () => {
  assert.deepEqual(
    assignmentsAvailableForEntry(assignments, [], "class-a").map((item) => item.id),
    ["math-assignment", "english-assignment"],
  );
});

test("create-result UI loads student-period availability and keeps editing in results", () => {
  const workspace = readFileSync(new URL("./ResultsWorkspace.jsx", import.meta.url), "utf8");

  assert.match(workspace, /student_id: form\.student_id/);
  assert.match(workspace, /academic_session_id: filters\.academic_session_id/);
  assert.match(workspace, /academic_term_id: filters\.academic_term_id/);
  assert.match(workspace, /assignmentsAvailableForEntry/);
  assert.match(workspace, /componentScoresForAssignment/);
  assert.match(workspace, /Use Back to\s+results to edit or reopen an existing result deliberately/);
  assert.match(workspace, /setForm\(\{ \.\.\.BLANK_FORM, student_id: form\.student_id \}\)/);
});
