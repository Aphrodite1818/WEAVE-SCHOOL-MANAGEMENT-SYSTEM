import assert from "node:assert/strict";
import test from "node:test";
import { createClassArms } from "./classArmBatch.js";
test("bulk arms use the selected level and deduplicate selections", async () => {
  const payloads = [];
  const result = await createClassArms(async (payload) => { payloads.push(payload); return payload; }, "level", ["A", "B", "A"]);
  assert.equal(result.created.length, 2);
  assert.deepEqual(result.failed, []);
  assert.deepEqual(payloads.map((p) => [p.academic_level_id, p.arm_label_id, p.teacher_membership_id]), [["level", "A", null], ["level", "B", null]]);
});
test("partial failure retains only failed arms for retry and continues the batch", async () => {
  const result = await createClassArms(async (payload) => {
    if (payload.arm_label_id === "B") throw new Error("Already exists");
    return payload;
  }, "level", ["A", "B", "C"]);
  assert.equal(result.created.length, 2);
  assert.deepEqual(result.failed.map((f) => f.armLabelId), ["B"]);
});

test("activation warning explains permanent structural locks and the editable name", async () => {
  const { readFile } = await import("node:fs/promises");
  const source = await readFile(new URL("./AcademicLevelsWorkspace.jsx", import.meta.url), "utf8");
  assert.match(source, /pendingAction\?\.action === "activate"/);
  assert.match(source, /Category, progression position, and department specialization timing become permanently locked/);
  assert.match(source, /even if you deactivate the level later/);
  assert.match(source, /You can still edit its name/);
});
