import assert from "node:assert/strict";
import test from "node:test";

import {
  filterAvailableItems,
  resolveFeatureAvailability,
} from "./featureAvailability.js";

const subscription = ({ planCode = "plus", guard = { allowed: true, pending: false } } = {}) => ({
  planCode,
  getFeatureGuard: () => guard,
});

test("runtime-disabled features are hidden everywhere", () => {
  const result = resolveFeatureAvailability(
    { runtimeFeature: "attendance" },
    { runtimeFeatures: { attendance: false } },
  );
  assert.equal(result.visible, false);
  assert.equal(result.reason, "runtime-disabled");
});

test("pending and denied subscription features are hidden", () => {
  assert.equal(
    resolveFeatureAvailability(
      { featureCode: "cbt_pairing" },
      { subscription: subscription({ guard: { allowed: true, pending: true } }) },
    ).visible,
    false,
  );
  assert.equal(
    resolveFeatureAvailability(
      { featureCode: "cbt_pairing" },
      { subscription: subscription({ guard: { allowed: false, pending: false } }) },
    ).visible,
    false,
  );
});

test("historical access can preserve a denied feature destination", () => {
  const result = resolveFeatureAvailability(
    { featureCode: "cbt_pairing", allowHistoricalAccess: true },
    {
      subscription: subscription({
        guard: { allowed: false, pending: false },
      }),
      historicalFeatures: { cbt_pairing: true },
    },
  );

  assert.equal(result.visible, true);
  assert.equal(result.reason, "historical-access");
});

test("free trial keeps bulk import out of navigation and tour surfaces", () => {
  const result = resolveFeatureAvailability(
    { featureCode: "bulk_import" },
    { subscription: subscription({ planCode: "free_trial" }) },
  );
  assert.equal(result.visible, false);
  assert.equal(result.reason, "plan-disabled");
});

test("account-scoped actors only see account-scoped destinations", () => {
  const visible = filterAvailableItems(
    [
      { to: "/teacher/classes" },
      { to: "/teacher/schools", accountScope: true },
    ],
    { isAccountScope: true },
  );
  assert.deepEqual(visible.map((item) => item.to), ["/teacher/schools"]);
});

test("legacy guide feature flags remain opt-in", () => {
  assert.equal(
    resolveFeatureAvailability(
      { feature: "attendance" },
      { entitledFeatures: { attendance: false } },
    ).visible,
    false,
  );
  assert.equal(
    resolveFeatureAvailability(
      { feature: "attendance" },
      { entitledFeatures: { attendance: true } },
    ).visible,
    true,
  );
});
