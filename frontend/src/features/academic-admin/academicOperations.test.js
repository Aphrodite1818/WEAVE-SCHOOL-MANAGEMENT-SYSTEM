import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { visibleGuideSteps } from "../guides/guideStepVisibility.js";
import { ROLE_GUIDES } from "../guides/roleGuideConfig.js";
import { termEntitlementLabel } from "../subscriptions/termEntitlementPresentation.js";

const source = (name) => readFile(new URL(name, import.meta.url), "utf8");

test("draft purchases remain scheduled even when entitlement status is active", () => {
  assert.equal(
    termEntitlementLabel(
      { status: "active" },
      { status: "draft", is_current: false },
    ),
    "Purchased · Scheduled",
  );
  assert.equal(
    termEntitlementLabel(
      { status: "active" },
      { status: "open", is_current: true },
    ),
    "Active for current term",
  );
  assert.equal(
    termEntitlementLabel(
      { status: "active" },
      { status: "closing", is_current: true },
    ),
    "Purchased for this term",
  );
  assert.equal(
    termEntitlementLabel(
      { status: "expired" },
      { status: "open", is_current: true },
    ),
    "expired",
  );
});

test("initial admin setup is the same three foundations on Free and paid plans", () => {
  for (const features of [
    undefined,
    { tenant_branding: false },
    { tenant_branding: true },
  ]) {
    const steps = visibleGuideSteps(ROLE_GUIDES.admin.steps, {
      runtimeFeatures: { attendance: false },
      features,
      role: "admin",
      completionMap: { departments: null },
    });
    assert.deepEqual(
      steps.map((step) => step.id),
      ["session", "term", "calendar"],
    );
    assert.ok(steps.every((step) => !step.optional && !step.feature));
  }
});

test("optional guide features still fail closed without their entitlement", () => {
  const steps = [
    { id: "school_logo", feature: "tenant_branding", optional: true },
  ];
  const options = { runtimeFeatures: { attendance: false }, role: "admin" };
  assert.deepEqual(visibleGuideSteps(steps, options), []);
  assert.deepEqual(
    visibleGuideSteps(steps, {
      ...options,
      features: { tenant_branding: false },
    }),
    [],
  );
  assert.deepEqual(
    visibleGuideSteps(steps, {
      ...options,
      features: { tenant_branding: true },
    }),
    steps,
  );
});

test("unreleased attendance stays out of every role guide", () => {
  for (const [role, config] of Object.entries(ROLE_GUIDES)) {
    const steps = visibleGuideSteps(config.steps, {
      role,
      runtimeFeatures: { attendance: false },
    });
    assert.ok(!steps.some((step) => step.id === "attendance"));
  }
});

test("specialization UI uses exact-term backend readiness and guards copying to DRAFT", async () => {
  const text = await source("ClassSpecializationWorkspace.jsx");
  assert.match(text, /getSpecializationWorkspace\(termId\)/);
  assert.match(text, /row\.specialization_required/);
  assert.match(text, /toLowerCase\(\) !== "draft"/);
  assert.match(text, /toLowerCase\(\) === "draft" && sourceTerms.length/);
  assert.doesNotMatch(
    text,
    /General|termPosition|specialization_required_from_term_position/,
  );
  assert.match(text, /failures\.join/);
  assert.match(text, /setClassDepartment\(id, termId, linkId\)/);
});

test("availability matrix and department catalog use one bulk read and only specialization-capable levels", async () => {
  const text = await source("DepartmentsWorkspace.jsx");
  assert.match(text, /departmentService\.getLevelAvailability\(\)/);
  assert.doesNotMatch(text, /getLevelDepartments\(/);
  assert.match(text, /Department availability by level/);
  assert.match(text, /Department catalog/);
  assert.match(text, /Available in/);
  assert.match(text, /levelSupportsSpecialization\(row\)/);
  assert.doesNotMatch(text, /title="Level availability"/);
  assert.match(
    text,
    /TypedConfirmationDialog open=\{Boolean\(pendingAction\)\}/,
  );
});

test("curriculum batch requires review and scopes departments only for specialization-capable levels", async () => {
  const text = await source("CurriculumWorkspace.jsx");
  assert.match(text, /\|\| !reviewing/);
  assert.match(text, /curriculumService\.addSubjects/);
  assert.match(text, /selectedSubjectIds\.map/);
  assert.match(text, /is_elective: elective/);
  assert.match(
    text,
    /academic_level_department_ids: specializationEnabled\s*\? addDepartmentIds\s*: \[\]/,
  );
  assert.match(text, /specializationEnabled\s*&&\s*levelDepartments\.length/);
  assert.match(
    text,
    /if \(!specializationEnabled \|\| !scopeSubjectId \|\| saving\) return/,
  );
  assert.match(
    text,
    /This level does not specialize\. Every curriculum subject is General/,
  );
  assert.match(text, /Already added/);
  assert.match(text, /Select all matching available subjects/);
  assert.match(text, /curriculumService\.deleteSubject\(pendingDelete\.id\)/);
  assert.match(text, /DELETE_CURRICULUM_SUBJECT/);
  assert.match(text, /Delete if unused/);
  assert.match(
    text,
    /teacher assignments, assignment history, or result records/,
  );
});

test("teacher multi-class assignment preserves backend eligibility and audit fields", async () => {
  const text = await source("TeacherAssignmentsWorkspace.jsx");
  assert.match(text, /curriculumService\s*\.getEligibleClasses/);
  assert.match(text, /class_ids: selectedClassIds/);
  assert.match(text, /Select all eligible/);
  assert.match(text, /academic_term_id: currentTermId/);
  assert.match(text, /reason: reason.trim\(\)/);
  assert.match(text, /beginAcademicSubmission/);
});
