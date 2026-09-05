import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("Academic Hub is an entity directory with a selected inspector and workflow navigation", async () => {
  const hub = await read("src/pages/admin/AcademicHubOverviewPage.jsx");
  const shell = await read("src/features/academic-admin/AcademicWorkflowShell.jsx");
  const orbit = await read("src/features/academic-admin/AcademicOrbitNavigator.jsx");

  assert.match(hub, /Academic entities/);
  assert.match(hub, /<table/);
  assert.match(hub, /selectedKey/);
  assert.match(hub, /selectedRow/);
  assert.match(hub, /Current scope/);
  assert.match(hub, /Lifecycle/);
  assert.match(hub, /AcademicOrbitNavigator/);

  assert.doesNotMatch(shell, /SearchableSelect/);
  assert.match(shell, /AcademicOrbitNavigator/);
  assert.match(orbit, /visibleWorkflows\.map/);
  assert.match(orbit, /academicWorkflowOrder/);
});

test("shared academic directories are list-first and keep editors secondary", async () => {
  const primitives = await read(
    "src/features/academic-admin/AcademicWorkspacePrimitives.jsx",
  );
  const classes = await read("src/features/academic-admin/ClassesWorkspace.jsx");
  const levels = await read("src/features/academic-admin/AcademicLevelsWorkspace.jsx");
  const arms = await read("src/features/academic-admin/ArmLabelsWorkspace.jsx");
  const departments = await read("src/features/academic-admin/DepartmentsWorkspace.jsx");
  const curriculum = await read("src/features/academic-admin/CurriculumWorkspace.jsx");

  assert.match(primitives, /selectedRecordId/);
  assert.match(primitives, /DefaultRecordInspector/);
  assert.match(primitives, /xl:sticky xl:top-4/);
  assert.match(primitives, /<table/);

  assert.match(classes, /Create class/);
  assert.match(classes, /showInspector={!showEditor}/);
  assert.match(levels, /Create level/);
  assert.match(levels, /showInspector={!showEditor}/);
  assert.match(arms, /Add arm label/);
  assert.match(arms, /showInspector={!showEditor}/);
  assert.match(departments, /Add department/);
  assert.match(departments, /Department catalog/);
  assert.match(departments, /<table/);
  assert.match(departments, /Available in/);
  assert.match(departments, /!editorOpen/);
  assert.match(curriculum, /editorMode/);
  assert.match(curriculum, /Add subject/);
  assert.match(curriculum, /Subject applicability/);
});

test("academic level confirmations mirror the backend contract instead of inventing typed phrases", async () => {
  const levels = await read("src/features/academic-admin/AcademicLevelsWorkspace.jsx");
  const service = await read("src/services/academicsService.js");

  assert.match(levels, /ConfirmDialog/);
  assert.doesNotMatch(levels, /TypedConfirmationDialog/);
  assert.doesNotMatch(levels, /ACTIVATE_ACADEMIC_LEVEL|DELETE_EMPTY_LEVEL/);
  assert.match(service, /activateLevel/);
  assert.match(service, /removeLevelFromSetup/);
});
