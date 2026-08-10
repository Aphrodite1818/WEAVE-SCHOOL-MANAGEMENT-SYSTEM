import assert from "node:assert/strict";
import test from "node:test";

import {
  componentScoreTotal,
  isAssessmentComplete,
  orderedAssessmentComponents,
} from "../../src/utils/assessmentResults.js";

test("supports different tenant component structures and persisted ordering", () => {
  const schoolA = orderedAssessmentComponents([
    { name: "Final Exam", position: 3, score: 60 },
    { name: "CA 1", position: 0, score: 8 },
    { name: "CA 2", position: 1, score: 9 },
    { name: "CA 3", position: 2, score: 7 },
  ]);
  const schoolB = [
    { name: "Assignment", position: 0, score: 17 },
    { name: "Midterm", position: 1, score: 24 },
    { name: "Final", position: 2, score: 41 },
  ];

  assert.deepEqual(schoolA.map((item) => item.name), ["CA 1", "CA 2", "CA 3", "Final Exam"]);
  assert.equal(componentScoreTotal(schoolA), 84);
  assert.equal(componentScoreTotal(schoolB), 82);
});

test("distinguishes an entered zero from a missing component score", () => {
  assert.equal(isAssessmentComplete([{ score: 0 }, { score: 10 }]), true);
  assert.equal(isAssessmentComplete([{ score: 0 }, { score: null }]), false);
  assert.equal(componentScoreTotal([{ score: 0 }, { score: null }]), 0);
});
