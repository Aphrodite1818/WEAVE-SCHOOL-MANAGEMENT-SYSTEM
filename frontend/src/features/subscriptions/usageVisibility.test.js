import assert from "node:assert/strict";
import test from "node:test";
import { shouldShowUsage } from "./usageVisibility.js";
test("unsupported empty resources are hidden but downgrade usage remains visible", () => {
  assert.equal(shouldShowUsage({ used: 0, limit: 0 }), false);
  assert.equal(shouldShowUsage({ used: 2, limit: 0 }), true);
  assert.equal(shouldShowUsage({ used: 0, limit: 5 }), true);
  assert.equal(shouldShowUsage({ used: 0, limit: null, is_unlimited: true }), true);
  assert.equal(shouldShowUsage(undefined), false);
});
