import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { termEntitlementLabel } from "../subscriptions/termEntitlementPresentation.js";
import { visibleGuideSteps } from "../guides/guideStepVisibility.js";
import { ROLE_GUIDES } from "../guides/roleGuideConfig.js";

const source = (name) => readFile(new URL(name, import.meta.url), "utf8");

test("draft purchases remain scheduled even when entitlement status is active", () => {
  assert.equal(termEntitlementLabel({ status: "active" }, { status: "draft", is_current: false }), "Purchased · Scheduled");
  assert.equal(termEntitlementLabel({ status: "active" }, { status: "open", is_current: true }), "Active for current term");
  assert.equal(termEntitlementLabel({ status: "active" }, { status: "closing", is_current: true }), "Purchased for this term");
  assert.equal(termEntitlementLabel({ status: "expired" }, { status: "open", is_current: true }), "expired");
});

test("Free onboarding excludes branding without removing required operational setup", () => {
  const steps = visibleGuideSteps(ROLE_GUIDES.admin.steps, { attendanceEnabled: false, features: { tenant_branding: false }, role: "admin", completionMap: { departments: null } });
  assert.ok(!steps.some((step) => step.id === "school_logo" || step.id === "departments"));
  for (const id of ["school_basics", "session", "term", "levels", "students", "teachers", "grading", "readiness"]) {
    assert.ok(steps.some((step) => step.id === id && !step.optional));
  }
});

test("released branding is optional for entitled schools; unknown entitlement fails closed", () => {
  const options = { attendanceEnabled: false, role: "admin" };
  assert.equal(visibleGuideSteps(ROLE_GUIDES.admin.steps, options).some((step) => step.feature), false);
  const branded = visibleGuideSteps(ROLE_GUIDES.admin.steps, { ...options, features: { tenant_branding: true } });
  assert.equal(branded.find((step) => step.id === "school_logo").optional, true);
});

test("unreleased attendance stays out of every role guide", () => {
  for (const [role, config] of Object.entries(ROLE_GUIDES)) {
    const steps = visibleGuideSteps(config.steps, { role, attendanceEnabled: false });
    assert.ok(!steps.some((step) => step.id === "attendance"));
  }
});

test("specialization UI uses exact-term backend readiness and guards copying to DRAFT", async () => {
  const text = await source("ClassSpecializationWorkspace.jsx");
  assert.match(text, /getSpecializationWorkspace\(termId\)/);
  assert.match(text, /row\.specialization_required/);
  assert.match(text, /toLowerCase\(\) !== "draft"/);
  assert.match(text, /toLowerCase\(\) === "draft" && sourceTerms.length/);
  assert.doesNotMatch(text, /General|termPosition|specialization_required_from_term_position/);
  assert.match(text, /failures\.join/);
  assert.match(text, /setClassDepartment\(id, termId, linkId\)/);
});

test("availability matrix and department table use one bulk read and guarded lifecycle actions", async () => {
  const text = await source("DepartmentsWorkspace.jsx");
  assert.match(text, /departmentService\.getLevelAvailability\(\)/);
  assert.doesNotMatch(text, /getLevelDepartments\(/);
  assert.match(text, /Department availability by level/);
  assert.match(text, /detailsLabel="Available levels"/);
  assert.match(text, /TypedConfirmationDialog open=\{Boolean\(pendingAction\)\}/);
});

test("curriculum batch requires review and sends elective and multiple department scopes together", async () => {
  const text = await source("CurriculumWorkspace.jsx");
  assert.match(text, /\|\| !reviewing/);
  assert.match(text, /curriculumService\.addSubjects/);
  assert.match(text, /selectedSubjectIds\.map/);
  assert.match(text, /is_elective: elective/);
  assert.match(text, /academic_level_department_ids: addDepartmentIds/);
  assert.match(text, /Already added/);
  assert.match(text, /Select all matching available subjects/);
});

test("teacher multi-class assignment preserves backend eligibility and audit fields", async () => {
  const text = await source("TeacherAssignmentsWorkspace.jsx");
  assert.match(text, /curriculumService\.getEligibleClasses/);
  assert.match(text, /class_ids: selectedClassIds/);
  assert.match(text, /Select all eligible classes/);
  assert.match(text, /academic_term_id: currentTermId/);
  assert.match(text, /reason: reason.trim\(\)/);
  assert.match(text, /beginAcademicSubmission/);
});
