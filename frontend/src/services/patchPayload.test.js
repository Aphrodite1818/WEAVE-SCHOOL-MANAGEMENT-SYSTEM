import assert from "node:assert/strict";
import test from "node:test";

import {
  buildChangedPatch,
  hasPatchChanges,
  mergePatchResult,
} from "./patchPayload.js";

test("buildChangedPatch sends only fields whose values changed", () => {
  const current = {
    first_name: "Taiwo",
    last_name: "Ayimora",
    state_of_origin: "Lagos",
  };

  assert.deepEqual(
    buildChangedPatch(current, {
      first_name: "Tayo",
      last_name: "Ayimora",
      state_of_origin: "Lagos",
    }),
    { first_name: "Tayo" },
  );
});

test("buildChangedPatch preserves explicit null when a nullable field is cleared", () => {
  const current = { description: "Existing description" };
  assert.deepEqual(buildChangedPatch(current, { description: null }), {
    description: null,
  });
});

test("buildChangedPatch drops unchanged explicit null values", () => {
  const current = { description: null, location: null };
  assert.deepEqual(
    buildChangedPatch(current, { description: null, location: null }),
    {},
  );
});

test("buildChangedPatch never treats undefined as update intent", () => {
  assert.deepEqual(
    buildChangedPatch(
      { first_name: "Taiwo", phone: "+2348012345678" },
      { first_name: undefined, phone: undefined },
    ),
    {},
  );
  assert.deepEqual(
    buildChangedPatch(null, { first_name: "Taiwo", phone: undefined }),
    { first_name: "Taiwo" },
  );
});

test("buildChangedPatch compares arrays and objects by value", () => {
  const current = {
    skipped_steps: ["one", "two"],
    metadata: { enabled: true },
  };
  assert.deepEqual(
    buildChangedPatch(current, {
      skipped_steps: ["one", "two"],
      metadata: { enabled: true },
    }),
    {},
  );
});

test("a missing baseline forwards supplied JSON values", () => {
  const payload = { first_name: "Taiwo", phone: null };
  assert.deepEqual(buildChangedPatch(null, payload), payload);
});

test("patch helpers identify no-op updates and merge successful responses", () => {
  assert.equal(hasPatchChanges({}), false);
  assert.equal(hasPatchChanges({ first_name: "Tayo" }), true);

  assert.deepEqual(
    mergePatchResult(
      { first_name: "Taiwo", last_name: "Ayimora" },
      { first_name: "Tayo" },
      { updated_at: "2026-08-19T10:00:00Z" },
    ),
    {
      first_name: "Tayo",
      last_name: "Ayimora",
      updated_at: "2026-08-19T10:00:00Z",
    },
  );
});
