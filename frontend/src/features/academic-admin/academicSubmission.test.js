import assert from "node:assert/strict";
import test from "node:test";
import { beginAcademicSubmission, endAcademicSubmission, finishAcademicCreation } from "./academicSubmission.js";

const event = (form, value = "another") => ({ currentTarget: form, preventDefault() {}, nativeEvent: { submitter: { value } } });

test("pending submissions are locked before React renders and can retry after failure", () => {
  const form = {};
  const first = beginAcademicSubmission(event(form));
  assert.ok(first);
  assert.equal(beginAcademicSubmission(event(form)), null);
  endAcademicSubmission(first);
  const retry = beginAcademicSubmission(event(form));
  assert.ok(retry);
  endAcademicSubmission(retry);
  assert.equal(beginAcademicSubmission(event(form), true), null);
});

test("save and add another resets entity fields, retains context, focuses and supports repeated creation", () => {
  const old = globalThis.requestAnimationFrame;
  globalThis.requestAnimationFrame = (callback) => callback();
  let focused = 0;
  let closed = 0;
  let formState = { level: "SS1", name: "A" };
  const form = { querySelector: () => ({ focus: () => focused++ }) };
  try {
    for (let i = 0; i < 2; i++) {
      const submission = beginAcademicSubmission(event(form));
      finishAcademicCreation(submission, () => { formState = { ...formState, name: "" }; }, () => closed++);
      endAcademicSubmission(submission);
      assert.deepEqual(formState, { level: "SS1", name: "" });
      formState.name = "B";
    }
    assert.equal(focused, 2);
    assert.equal(closed, 0);
  } finally { globalThis.requestAnimationFrame = old; }
});

test("save and close and edits close without performing create reset", () => {
  for (const [intent, editing] of [["close", false], ["another", true]]) {
    let closed = 0;
    const submission = beginAcademicSubmission(event({}, intent));
    finishAcademicCreation(submission, () => assert.fail("create reset must not run"), () => closed++, editing);
    assert.equal(closed, 1);
    endAcademicSubmission(submission);
  }
});
