import assert from "node:assert/strict";
import test from "node:test";

import {
  categorySupportsDepartments,
  filterDepartmentWorkflow,
  normalizeSpecializationTermPosition,
  supportsDepartmentWorkflow,
} from "./academicDepartmentCapability.js";

const primaryCategories = [
  { value: "KINDERGARTEN", supports_departments: false },
  { value: "NURSERY", supports_departments: false },
  { value: "PRIMARY", supports_departments: false },
];

const secondaryCategories = [
  { value: "JUNIOR_SECONDARY", supports_departments: false },
  { value: "SENIOR_SECONDARY", supports_departments: true },
];

test("department workflow is hidden when no institution category supports it", () => {
  const workflows = ["levels", "classes", "departments", "subjects"];

  assert.equal(supportsDepartmentWorkflow(primaryCategories), false);
  assert.deepEqual(filterDepartmentWorkflow(workflows, primaryCategories), [
    "levels",
    "classes",
    "subjects",
  ]);
});

test("department workflow remains available when an institution category supports it", () => {
  const workflows = ["levels", "classes", "departments", "subjects"];

  assert.equal(supportsDepartmentWorkflow(secondaryCategories), true);
  assert.deepEqual(
    filterDepartmentWorkflow(workflows, secondaryCategories),
    workflows,
  );
});

test("department capability remains scoped to the selected academic category", () => {
  assert.equal(
    categorySupportsDepartments(secondaryCategories, "JUNIOR_SECONDARY"),
    false,
  );
  assert.equal(
    categorySupportsDepartments(secondaryCategories, "SENIOR_SECONDARY"),
    true,
  );
});

test("specialization requirement is normalized only for department-enabled categories", () => {
  assert.equal(
    normalizeSpecializationTermPosition(
      secondaryCategories,
      "SENIOR_SECONDARY",
      "2",
    ),
    2,
  );
  assert.equal(
    normalizeSpecializationTermPosition(
      secondaryCategories,
      "SENIOR_SECONDARY",
      "",
    ),
    null,
  );
  assert.equal(
    normalizeSpecializationTermPosition(
      secondaryCategories,
      "JUNIOR_SECONDARY",
      "1",
    ),
    null,
  );
});
