import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("mobile term upgrades preserve the same dedicated tour handoff as desktop", async () => {
  const source = await read(
    "src/pages/admin/ResponsiveSubscriptionOptionsPage.jsx",
  );
  const mobileStart = source.indexOf("function MobileSubscriptionOptionsPage()");
  const mobileEnd = source.indexOf("function getActionLabel", mobileStart);
  const mobile = source.slice(mobileStart, mobileEnd);

  assert.ok(mobileStart >= 0 && mobileEnd > mobileStart);
  assert.match(source, /savePendingUpgradeTour/);
  assert.match(mobile, /getTermPlanHistory\(\)/);
  assert.match(mobile, /upgradeTourForPlan\(\{/);
  assert.match(mobile, /history:\s*planHistory/);
  assert.match(
    mobile,
    /saveTermPaymentIntent\(\{[\s\S]*?postPaymentAction,[\s\S]*?upgradeTour,/,
  );
  assert.match(
    mobile,
    /refreshSubscriptionState\(\{ silent: true \}\);[\s\S]*?savePendingUpgradeTour\(\{ \.\.\.upgradeTour, dedicated: true \}\)/,
  );
});

test("pending admin upgrade tours open on the return workspace instead of waiting for dashboard", async () => {
  const source = await read("src/features/guides/useWorkspaceTour.js");
  const consumeAt = source.indexOf("const pending = consumePendingUpgradeTour();");
  const effectStart = source.lastIndexOf("useEffect(() => {", consumeAt);
  const effectEnd = source.indexOf("useEffect(() => {", consumeAt + 1);
  const upgradeEffect = source.slice(effectStart, effectEnd);

  assert.ok(consumeAt >= 0 && effectStart >= 0 && effectEnd > consumeAt);
  assert.match(
    upgradeEffect,
    /role !== "admin" \|\| !pathname\.startsWith\("\/admin\/"\)/,
  );
  assert.doesNotMatch(upgradeEffect, /pathname !== "\/admin\/dashboard"/);
  assert.match(upgradeEffect, /setDedicated\(true\)/);
  assert.match(upgradeEffect, /setOpen\(true\)/);
});
