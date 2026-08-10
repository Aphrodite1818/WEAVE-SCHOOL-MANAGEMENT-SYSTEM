import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "../..");

const readSource = (relativePath) =>
  readFile(path.join(frontendRoot, relativePath), "utf8");

test("bulk import uses the shared authenticated transport and deduplicates polling", async () => {
  const source = await readSource("src/services/bulkImport.service.js");

  assert.match(source, /api\.postForm\(/);
  assert.match(source, /api\.getBlob\(/);
  assert.match(source, /inFlightJobRequests/);
  assert.match(source, /ERROR_POLL_CACHE_MS/);
  assert.doesNotMatch(source, /\bfetch\s*\(/);
});

test("subscription guards do not treat missing entitlements as confirmed access", async () => {
  const source = await readSource("src/features/subscriptions/SubscriptionProvider.jsx");

  assert.match(source, /visibleErrors\.entitlements/);
  assert.match(source, /allowed:\s*false,[\s\S]*We couldn't confirm access for this feature/);
  assert.match(source, /allowed:\s*false,[\s\S]*We couldn't confirm your plan limits/);
});

test("subscription lifecycle prompt waits until grace and uses tenant-brand styling", async () => {
  const providerSource = await readSource("src/features/subscriptions/SubscriptionProvider.jsx");
  const promptSource = await readSource("src/features/subscriptions/SubscriptionLifecyclePrompt.jsx");
  const modalSource = await readSource("src/components/ui/Modal.jsx");

  assert.match(providerSource, /<SubscriptionLifecyclePrompt/);
  assert.match(
    providerSource,
    /const statusCode =\s*visibleCurrentSubscription\?\.status \|\|\s*visibleEntitlements\?\.subscription_status/,
  );
  assert.match(promptSource, /const PROMPTABLE_STATUSES = new Set\(\[\s*"grace_period",\s*"expired",\s*"cancelled",\s*\]\)/);
  assert.doesNotMatch(promptSource, /PROMPTABLE_STATUSES[\s\S]{0,120}"past_due"/);
  assert.match(promptSource, /title: "Subscription paused"/);
  assert.match(promptSource, /description=\{content\.description\}/);
  assert.match(promptSource, /border-primary\/20 bg-primary-subtle\/50/);
  assert.match(promptSource, /bg-primary\/10 text-primary/);
  assert.match(promptSource, /<Icon className="h-5 w-5"/);
  assert.match(promptSource, /navigate\("\/admin\/billing\/plans"\)/);
  assert.match(promptSource, /placement="center"/);
  assert.match(promptSource, /sessionStorage/);
  assert.match(modalSource, /items-center justify-center/);
  assert.match(modalSource, /window\.visualViewport/);
});

test("registration checkout prompt is exclusive to a resolved trialing subscription", async () => {
  const source = await readSource("src/components/layout/DashboardLayout.jsx");

  assert.match(source, /const subscriptionStateResolved = Boolean\(currentSubscription \|\| entitlements\)/);
  assert.match(
    source,
    /const registrationCheckoutEligible = Boolean\([\s\S]*subscriptionStateResolved && activeSubscriptionStatus === "trialing"[\s\S]*\);/,
  );
  assert.match(
    source,
    /const registrationCheckoutOpen = Boolean\([\s\S]*onboardingModalEnabled &&[\s\S]*registrationCheckoutEligible &&[\s\S]*registrationCheckoutPlanCode &&[\s\S]*!registrationCheckoutSatisfied/,
  );
});

test("simulation lab exposes scheduled downgrade timeline controls", async () => {
  const source = await readSource("src/pages/superadmin/SuperadminSimulationPage.jsx");

  assert.match(source, /downgrade_effective_in_days/);
  assert.match(source, /downgrade_due_now/);
  assert.match(source, /state\.plan_change/);
  assert.match(source, /Effective date/);
  assert.match(source, /downgrade awaiting payment/);
  assert.match(source, /downgrade blocked/);
});

test("simulation lab exposes a one-step enter-grace lifecycle action", async () => {
  const source = await readSource("src/pages/superadmin/SuperadminSimulationPage.jsx");

  assert.match(source, /const ENTER_GRACE_SCENARIO = "enter_grace_period"/);
  assert.match(source, /label: "Enter grace period now"/);
  assert.match(source, /scenario: "period_ended"/);
  assert.match(source, /reconcileSubscription\(normalizedTenantId\)/);
  assert.match(source, /currentState\.status === "active"/);
  assert.match(source, /currentState\.status !== "past_due"/);
  assert.match(source, /result\.state\.status !== "grace_period"/);
  assert.match(source, /Subscription entered grace period\./);
});

test("modal traps keyboard focus and restores the previously focused element", async () => {
  const source = await readSource("src/components/ui/Modal.jsx");

  assert.match(source, /FOCUSABLE_SELECTOR/);
  assert.match(source, /previouslyFocusedRef/);
  assert.match(source, /event\.key !== "Tab"/);
  assert.match(source, /previous\.focus\(\{ preventScroll: true \}\)/);
  assert.match(source, /tabIndex=\{-1\}/);
});

test("calendar actions use toast success feedback instead of an inline success banner", async () => {
  const source = await readSource("src/features/schoolCalendar/components/SchoolCalendarWorkspace.jsx");

  assert.match(source, /useToast/);
  assert.match(source, /showSuccess\(successMessage\)/);
  assert.doesNotMatch(source, /setMessage\(/);
  assert.doesNotMatch(source, /<Notice tone="success"/);
});

test("invitation feedback avoids transport and queue terminology", async () => {
  const source = await readSource("src/pages/admin/AdminInvitationPage.jsx");

  assert.match(source, /Invitation created and ready for delivery\./);
  assert.match(source, /invitation is on its way\./);
  assert.doesNotMatch(source, /accepted by the API/i);
  assert.doesNotMatch(source, /Queueing invitation/i);
  assert.doesNotMatch(source, /delivery remains asynchronous/i);
});

test("student creation copy describes outcomes instead of implementation details", async () => {
  const source = await readSource("src/pages/admin/StudentCreatePage.jsx");

  assert.match(source, /admission number and first-login code are created automatically/i);
  assert.match(source, /Parent invitations are on their way\./);
  assert.doesNotMatch(source, /generated by the backend/i);
  assert.doesNotMatch(source, /invitations queued/i);
  assert.doesNotMatch(source, /atomically/i);
});

test("session restoration uses one dedicated responsive bootstrap presentation", async () => {
  const loginSource = await readSource("src/pages/public/LoginPage.jsx");
  const bootstrapSource = await readSource("src/components/layout/SessionBootstrapScreen.jsx");

  assert.match(loginSource, /return <SessionBootstrapScreen \/>/);
  assert.doesNotMatch(loginSource, /Getting your workspace ready/);
  assert.doesNotMatch(loginSource, /title="Restoring session"/);
  assert.match(bootstrapSource, /min-h-\[100dvh\]/);
  assert.match(bootstrapSource, /env\(safe-area-inset-top\)/);
  assert.match(bootstrapSource, /env\(safe-area-inset-bottom\)/);
  assert.match(bootstrapSource, /Restoring your session…/);
  assert.equal((bootstrapSource.match(/<Spinner/g) || []).length, 1);
});
