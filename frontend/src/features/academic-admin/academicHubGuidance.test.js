import assert from "node:assert/strict";
import test from "node:test";

import { chooseAcademicHubNextAction } from "./academicHubGuidance.js";

test("asks admins to create or open a session before other academic work", () => {
  const action = chooseAcademicHubNextAction({}, true);

  assert.equal(action.action, "Create or open the current academic session");
  assert.equal(action.to, "/admin/academic/sessions");
});

test("prioritizes submitted results after core setup exists", () => {
  const action = chooseAcademicHubNextAction(
    {
      active_academic_session: "2026/2027",
      active_academic_term: "First Term",
      total_classes: 3,
      total_subjects: 12,
      result_rows_submitted: 8,
      report_cards_generated: 0,
      report_cards_published: 0,
    },
    true,
  );

  assert.equal(action.action, "Review submitted results");
  assert.equal(action.to, "/admin/academic/results?view=submitted");
});

test("moves administrators to session closure when no earlier blocker exists", () => {
  const action = chooseAcademicHubNextAction(
    {
      active_academic_session: "2026/2027",
      active_academic_term: "First Term",
      total_classes: 3,
      total_subjects: 12,
      result_rows_submitted: 0,
      report_cards_generated: 5,
      report_cards_published: 5,
    },
    true,
  );

  assert.equal(action.action, "Review the session closure checklist");
  assert.equal(action.to, "/admin/academic/sessions?view=closing");
});
