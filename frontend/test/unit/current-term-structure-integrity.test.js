import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { createClassArms } from "../../src/features/academic-admin/classArmBatch.js";
import {
  currentOpenTerm,
  currentTermDepartmentRequirement,
  specializationIsActiveForTerm,
} from "../../src/features/academic-admin/currentTermStructureIntegrity.js";

const frontendRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const readSource = (...segments) =>
  fs.readFileSync(path.join(frontendRoot, "src", ...segments), "utf8");

const firstTerm = { id: "term-1", name: "first_term", status: "open", is_current: true };
const ss1 = {
  id: "ss1",
  name: "SS1",
  specialization_required_from_term_position: 1,
};

test("specialization only becomes mandatory when the configured term threshold is reached", () => {
  assert.equal(specializationIsActiveForTerm(ss1, firstTerm), true);
  assert.equal(
    specializationIsActiveForTerm(
      { ...ss1, specialization_required_from_term_position: 2 },
      firstTerm,
    ),
    false,
  );
});

test("current open term ignores draft or non-current terms", () => {
  assert.equal(
    currentOpenTerm([
      { id: "draft", name: "second_term", status: "draft", is_current: false },
      firstTerm,
    ]).id,
    "term-1",
  );
});

test("specializing level is blocked in the UI until an active level department exists", () => {
  const requirement = currentTermDepartmentRequirement({
    level: ss1,
    term: firstTerm,
    availability: [],
  });
  assert.equal(requirement.required, true);
  assert.equal(requirement.blocked, true);
  assert.deepEqual(requirement.options, []);
});

test("active level departments become current-term class choices", () => {
  const requirement = currentTermDepartmentRequirement({
    level: ss1,
    term: firstTerm,
    availability: [
      {
        id: "science-link",
        academic_level_id: "ss1",
        department_name: "Science",
        is_active: true,
        archived_at: null,
      },
    ],
  });
  assert.equal(requirement.blocked, false);
  assert.deepEqual(requirement.options, [
    { value: "science-link", label: "Science" },
  ]);
});

test("batch class creation carries one selected current-term department to every arm", async () => {
  const payloads = [];
  const result = await createClassArms(
    async (payload) => {
      payloads.push(payload);
      return payload;
    },
    "ss1",
    ["a", "b"],
    { current_term_department_id: "science-link" },
  );

  assert.equal(result.created.length, 2);
  assert.deepEqual(
    payloads.map((payload) => payload.current_term_department_id),
    ["science-link", "science-link"],
  );
});

test("class workspace requires current-term specialization before making classes active", () => {
  const source = readSource("features", "academic-admin", "ClassesWorkspace.jsx");
  assert.match(source, /Department for \$\{termLabel\(currentTerm\)\}/);
  assert.match(source, /formSpecialization\.blocked/);
  assert.match(source, /current_term_department_id/);
  assert.match(source, /Assign and activate/);
  assert.match(source, /curriculumService\.getClassDepartment/);
});

test("academic level activation shows an explicit structural lock warning", () => {
  const source = readSource(
    "features",
    "academic-admin",
    "AcademicLevelsWorkspace.jsx",
  );
  assert.match(source, /AlertTriangle/);
  assert.match(source, /Activate academic level carefully/);
  assert.match(source, /This is a structural commitment/);
  assert.match(source, /I checked it — activate/);
});
