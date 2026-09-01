import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const sourceRoot = path.dirname(fileURLToPath(import.meta.url));
const readSource = (...segments) =>
  fs.readFileSync(path.join(sourceRoot, ...segments), "utf8");

test("installed mobile navigation stays close to the device bottom edge", () => {
  const css = readSource("styles", "mobileOverrides.css");

  assert.match(
    css,
    /bottom:\s*calc\(-0\.45\s*\*\s*env\(safe-area-inset-bottom\)\)\s*!important/,
  );
  assert.match(
    css,
    /calc\(env\(safe-area-inset-bottom\)\s*\*\s*0\.45\)/,
  );
});

test("academic structure is not coupled to class or subject subscription quotas", () => {
  const setupPage = readSource("pages", "admin", "AdminGettingStartedPage.jsx");
  const pricing = readSource("features", "subscriptions", "subscriptionConfig.js");

  assert.doesNotMatch(setupPage, /resource_limit_reached/);
  assert.doesNotMatch(setupPage, /Plan limit reached/);
  assert.doesNotMatch(pricing, /resource:\s*["'](?:classes|subjects)["']/);
});

test("admin guided setup keeps configuration inside the selected step", () => {
  const overview = readSource("pages", "admin", "AdminGettingStartedPage.jsx");
  const stepPage = readSource("pages", "admin", "AdminGettingStartedStepPage.jsx");
  const workspace = readSource("features", "guides", "AdminGuideTaskWorkspace.jsx");

  assert.match(overview, /navigate\(`\/admin\/getting-started\/\$\{step\.id\}`\)/);
  assert.match(stepPage, /<AdminGuideTaskWorkspace stepId=\{step\.id\}/);
  assert.doesNotMatch(stepPage, /navigate\(step\.to\)/);
  assert.match(stepPage, /Previous:/);
  assert.match(stepPage, /Skip for now/);
  assert.match(stepPage, /Next:/);
  assert.match(workspace, /levels: \{ kind: "levels", activeTab: "create" \}/);
  assert.match(workspace, /assignments: \{ kind: "assignments", activeTab: "assign" \}/);
  assert.match(workspace, /calendar: \{ kind: "calendar", activeTab: "setup" \}/);
});

test("academic level categories come from the institution-scoped backend catalog", () => {
  const levelsWorkspace = readSource(
    "features",
    "academic-admin",
    "AcademicLevelsWorkspace.jsx",
  );
  const academicsService = readSource("services", "academicsService.js");

  assert.match(academicsService, /getCategories: \(\) => api\.get\("\/academic-levels\/categories"\)/);
  assert.match(levelsWorkspace, /academicLevelService\.getCategories\(\)/);
  assert.match(levelsWorkspace, /categoryOptions\.map/);
  assert.doesNotMatch(levelsWorkspace, /value: "JUNIOR_SECONDARY"/);
  assert.doesNotMatch(levelsWorkspace, /value: "SENIOR_SECONDARY"/);
});

test("assisted term opening keeps plan choice inside authenticated term flow", () => {
  const academicSetup = readSource(
    "features",
    "academic-admin",
    "AcademicSetupWorkspace.jsx",
  );
  const registerPage = readSource("pages", "public", "RegisterPage.jsx");
  const plansPage = readSource("pages", "admin", "SubscriptionOptionsPage.jsx");

  assert.match(academicSetup, /TERM_PLAN_ACTIVATION_REQUIRED/);
  assert.match(academicSetup, /plan_code: termPlanPrompt\.suggested_plan/);
  assert.match(academicSetup, /window\.location\.assign\(subscriptionService\.checkoutRedirectUrl\(checkout\)\)/);
  assert.match(academicSetup, /billing\/plans\?term=/);
  assert.doesNotMatch(registerPage, /selectedPlan\?\.planCode/);
  assert.doesNotMatch(registerPage, /initial_plan_intent/);
  assert.match(plansPage, /option\.plan_code === "free"/);
  assert.match(plansPage, /activateFreeTerm\(term\.id\)/);
});

test("internal billing keeps staging visuals with term-based behavior", () => {
  const mobilePlans = readSource(
    "pages",
    "admin",
    "ResponsiveSubscriptionOptionsPage.jsx",
  );
  const billingPage = readSource("pages", "admin", "BillingPage.jsx");

  assert.match(mobilePlans, /import SubscriptionOptionsPage/);
  assert.match(mobilePlans, /MobileSubscriptionOptionsPage/);
  assert.match(mobilePlans, /data-mobile-billing-page="true"/);
  assert.match(mobilePlans, /getTermPlanOptions/);
  assert.match(mobilePlans, /amount_due_kobo/);
  assert.match(mobilePlans, /saveTermPaymentIntent/);
  assert.match(billingPage, /Term plan/);
  assert.match(billingPage, /dashboard-welcome-blue/);
  assert.match(billingPage, /Plan record/);
  assert.match(billingPage, /Term history/);
  assert.match(billingPage, /Payment history/);
  assert.doesNotMatch(billingPage, /automatic renewal/i);
});

test("new tenant admins enter assisted setup immediately after onboarding", () => {
  const onboardingGate = readSource(
    "components",
    "layout",
    "useOnboardingGate.js",
  );

  assert.match(onboardingGate, /GETTING_STARTED_ROUTE_BY_ROLE\[normalizedRole\]/);
  assert.match(onboardingGate, /profileMode === "onboarding"/);
  assert.match(
    onboardingGate,
    /admin: "\/admin\/getting-started"/,
  );
});

test("linked-school role guides auto-show once with the intended persistence scope", () => {
  const onboardingGate = readSource(
    "components",
    "layout",
    "useOnboardingGate.js",
  );
  const dashboardLayout = readSource("components", "layout", "DashboardLayout.jsx");
  const guideService = readSource("services", "guideService.js");

  assert.match(onboardingGate, /teacher: "\/teacher\/getting-started"/);
  assert.match(onboardingGate, /parent: "\/parent\/getting-started"/);
  assert.match(onboardingGate, /student: "\/student\/getting-started"/);
  assert.match(onboardingGate, /completedInitialOnboarding/);
  assert.match(dashboardLayout, /hasValidSchoolContext/);
  assert.match(dashboardLayout, /role === "admin" \|\| Boolean\(user\.tenant_id\)/);
  assert.match(guideService, /user\.meta\?\.teacher_account_id/);
  assert.match(guideService, /user\.meta\?\.parent_account_id/);
  assert.match(guideService, /accountScoped\s*\? "global"/);
});

test("tenant admin guide exits always leave the full-screen setup shell", () => {
  const setupRoute = readSource("routes", "AdminGettingStartedRoute.jsx");
  const adminRoutes = readSource("routes", "adminRoutes.jsx");
  const roleGuide = readSource("features", "guides", "useRoleGuide.js");

  assert.match(setupRoute, /label === "finish later"/);
  assert.match(setupRoute, /label === "complete setup"/);
  assert.match(setupRoute, /label === "back to dashboard"/);
  assert.match(setupRoute, /await finish\(\)/);
  assert.match(setupRoute, /leaveAdminSetup\("\/admin\/dashboard"\)/);
  assert.match(roleGuide, /!hasGuideExitSuppression\(role\)/);
  assert.match(
    adminRoutes,
    /path="\/admin\/getting-started"[\s\S]*element=\{<AdminGettingStartedRoute \/>\}/,
  );
});

test("other actor guide exits return to the configured dashboard", () => {
  const roleGuide = readSource("pages", "shared", "RoleGettingStartedPage.jsx");

  assert.match(roleGuide, /navigate\(guide\.config\.dashboardRoute, \{ replace: true \}\)/);
  assert.match(roleGuide, /onClick=\{\(\) => navigate\(guide\.config\.dashboardRoute\)\}/);
});

test("terminal guide completion must be confirmed before leaving setup", () => {
  const guideService = readSource("services", "guideService.js");
  const setupRoute = readSource("routes", "AdminGettingStartedRoute.jsx");

  assert.match(guideService, /const terminalWrite = TERMINAL_STATUSES\.has\(requestedStatus\)/);
  assert.match(guideService, /ensureTerminalConfirmation\(requestedStatus, response\)/);
  assert.match(guideService, /throw error;/);
  assert.doesNotMatch(setupRoute, /finally\s*\{\s*leaveAdminSetup/);
  assert.match(
    setupRoute,
    /await finish\(\);\s*leaveAdminSetup\("\/admin\/dashboard"\)/,
  );
});

test("teacher and parent guide fallback state is account-global while student and admin stay tenant-scoped", () => {
  const guideService = readSource("services", "guideService.js");

  assert.match(guideService, /"teacher_account"/);
  assert.match(guideService, /"parent_account"/);
  assert.match(guideService, /const tenant = accountScoped\s*\? "global"/);
  assert.match(guideService, /user\.tenant_id/);
});

test("a failed guide-state read cannot auto-classify a user as a fresh guide", () => {
  const guideService = readSource("services", "guideService.js");
  const roleGuide = readSource("features", "guides", "useRoleGuide.js");

  assert.match(
    guideService,
    /catch \{\s*return persistFallback\(guideKey, \{\s*\.\.\.localState,\s*sync_pending: true,/,
  );
  assert.match(roleGuide, /!syncPending/);
});
