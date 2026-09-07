import assert from "node:assert/strict";
import test from "node:test";

import { adminSchoolYearCompletion } from "./adminSchoolYearCompletion.js";
import { schoolYearProgress } from "./schoolYearProgress.js";

test("term milestone stays incomplete until its session is current and open", () => {
  const completion = adminSchoolYearCompletion({
    completion: { session: true, term: true, calendar: false },
    session_status: "draft",
    session_is_current: false,
  });

  assert.equal(completion.session, true);
  assert.equal(completion.term, false);
  assert.equal(schoolYearProgress(completion).nextStep, "term");
  assert.equal(schoolYearProgress(completion).canOpen("calendar"), false);
});

test("calendar unlocks after first term exists and session opening succeeds", () => {
  const completion = adminSchoolYearCompletion({
    completion: { session: true, term: true, calendar: false },
    session_status: "open",
    session_is_current: true,
  });

  assert.equal(completion.term, true);
  assert.equal(schoolYearProgress(completion).nextStep, "calendar");
  assert.equal(schoolYearProgress(completion).canOpen("calendar"), true);
});

test("basic setup completes on active calendar without requiring the term to open", () => {
  const completion = adminSchoolYearCompletion({
    completion: { session: true, term: true, calendar: true, start_term: false },
    session_status: "open",
    session_is_current: true,
    term_status: "draft",
    term_is_current: false,
  });

  const progress = schoolYearProgress(completion);
  assert.equal(progress.complete, true);
  assert.equal(progress.nextStep, null);
});
