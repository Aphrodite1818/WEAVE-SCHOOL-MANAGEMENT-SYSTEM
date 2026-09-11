import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("public pricing explains permanent Free without rendering a Free pricing card", async () => {
  const [config, landing, pricing] = await Promise.all([
    read("src/features/subscriptions/subscriptionConfig.js"),
    read("src/pages/public/LandingPage.jsx"),
    read("src/pages/public/PricingPage.jsx"),
  ]);

  assert.match(
    config,
    /PLAN_ORDER\s*=\s*\["free",\s*"plus",\s*"professional",\s*"enterprise"\]/,
  );
  assert.match(config, /normalized === "free_trial"\) return "free"/);
  assert.match(config, /if \(value === null\) return "Unlimited"/);
  assert.match(config, /if \(value === undefined\) return "—"/);
  assert.match(
    landing,
    /Free is permanent\. Registration never starts a payment\./,
  );
  assert.match(landing, /plan\.planCode !== "free"/);
  assert.match(pricing, /plan\.planCode !== "free"/);
  assert.doesNotMatch(landing, /Current plan/);
  assert.doesNotMatch(landing, /From ₦80,000/);
  assert.match(pricing, /Free is a permanent Weave plan|Permanent Free/);
  assert.doesNotMatch(pricing, /30-day free trial/i);
});

test("registration stays independent from public pricing choices and payment", async () => {
  const source = await read("src/pages/public/RegisterPage.jsx");

  assert.match(source, /tenantService\.registerTenant/);
  assert.doesNotMatch(source, /selectedPlan|initial_plan_intent/);
  assert.doesNotMatch(source, /initializeTermCheckout/);
  assert.doesNotMatch(source, /Paystack/);
});

test("academic term opening uses the plan-selection contract", async () => {
  const source = await read(
    "src/features/academic-admin/AcademicSetupWorkspace.jsx",
  );

  assert.match(source, /TERM_PLAN_SELECTION_REQUIRED/);
  assert.match(source, /Choose a plan for/);
  assert.match(source, /Use Free for this term/);
  assert.match(source, /Compare all plans/);
  assert.match(source, /intent=open-term&origin=academic-terms/);
  assert.doesNotMatch(source, /title="Pay for term"/);
});

test("internal plan management uses one backend-driven responsive page", async () => {
  const [responsive, plans, routes] = await Promise.all([
    read("src/pages/admin/ResponsiveSubscriptionOptionsPage.jsx"),
    read("src/pages/admin/SubscriptionOptionsPage.jsx"),
    read("src/routes/adminRoutes.jsx"),
  ]);

  assert.match(responsive, /export default ResponsiveSubscriptionOptionsPage/);
  assert.match(responsive, /matchMedia/);
  assert.match(responsive, /MobileSubscriptionOptionsPage/);
  assert.match(responsive, /grid grid-cols-2 gap-3/);
  assert.doesNotMatch(responsive, /col-span-2/);
  assert.match(plans, /getTermPlanOptions/);
  assert.match(plans, /option\.blockers/);
  assert.match(plans, /<Modal/);
  assert.match(plans, /Checkout\s+has not started/);
  assert.doesNotMatch(plans, /term-plan-feedback/);
  assert.doesNotMatch(plans, /This school does not currently fit/);
  assert.match(plans, /amount_due_kobo/);
  assert.doesNotMatch(plans, /PLAN_RANK/);

  const shellIndex = routes.indexOf(
    '<Route element={<DashboardShell role="admin" />}>',
  );
  const planRouteIndex = routes.indexOf('path="/admin/billing/plans"');
  const shellCloseIndex = routes.lastIndexOf("</Route>");
  assert.ok(shellIndex >= 0);
  assert.ok(planRouteIndex > shellIndex);
  assert.ok(planRouteIndex < shellCloseIndex);
});

test("payment verification preserves the originating workflow", async () => {
  const [service, verify] = await Promise.all([
    read("src/services/subscriptionService.js"),
    read("src/pages/admin/SubscriptionVerifyPage.jsx"),
  ]);

  assert.match(service, /saveTermPaymentIntent/);
  assert.match(service, /postPaymentAction/);
  assert.match(service, /returnPath/);
  assert.match(service, /origin: "academic-terms"/);
  assert.match(verify, /consumeTermPaymentIntent/);
  assert.match(verify, /open_term/);
  assert.match(verify, /openTerm/);
});

test("billing derives the current operational term instead of any active history row", async () => {
  const source = await read("src/pages/admin/BillingPage.jsx");

  assert.match(source, /is_current/);
  assert.match(source, /String\(term.status \|\| ""\).toLowerCase\(\) === "open"/);
  assert.match(source, /entitlements\?\.plan/);
  assert.doesNotMatch(
    source,
    /history\.find\(\(item\)\s*=>\s*item\.status\s*===\s*"active"\)/,
  );
});
