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
  assert.match(stepPage, /<AdminGuideTaskWorkspace\s+stepId=\{step\.id\}/);
  assert.doesNotMatch(stepPage, /navigate\(step\.to\)/);
  assert.match(stepPage, /SchoolYearProgress/);
  assert.match(stepPage, /progress\.canOpen\(step\.id\)/);
  assert.match(stepPage, /Continue to/);
  assert.doesNotMatch(stepPage, /Skip for now|What this page controls/);
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

test("academic lifecycle status icons use semantic colors, not tenant branding", () => {
  const primitives = readSource(
    "features",
    "academic-admin",
    "AcademicWorkspacePrimitives.jsx",
  );

  assert.match(primitives, /const lifecycleStatusMeta = \(status\) =>/);
  assert.match(primitives, /"text-success"/);
  assert.match(primitives, /"text-error"/);
  assert.match(primitives, /"text-warning"/);
  assert.match(primitives, /value === "archived" \? Archive : AlertTriangle/);
  assert.doesNotMatch(primitives, /h-4 w-4 shrink-0 text-primary/);
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

test("paid-only admin features are hidden instead of rendered for ineligible plans", () => {
  const sidebar = readSource("components", "layout", "Sidebar.jsx");
  const navConfig = readSource("components", "layout", "navConfig.js");
  const adminRoutes = readSource("routes", "adminRoutes.jsx");
  const settingsPage = readSource("pages", "shared", "RoleSettingsPage.jsx");
  const analyticsPage = readSource("pages", "shared", "RoleAnalyticsPage.jsx");
  const adminDashboard = readSource("pages", "admin", "AdminDashboardPage.jsx");

  assert.match(sidebar, /isFeatureAvailable\(item,/);
  assert.match(navConfig, /featureCode: FEATURE_CODES\.CBT_PAIRING/);
  assert.match(adminRoutes, /SubscriptionFeatureRouteGuard featureCode=\{FEATURE_CODES\.CBT_PAIRING\}/);
  assert.match(adminRoutes, /SubscriptionFeatureRouteGuard featureCode=\{FEATURE_CODES\.TENANT_BRANDING\}/);
  assert.match(settingsPage, /tenantBrandingGuard\.allowed/);
  assert.match(settingsPage, /!tenantBrandingGuard\.pending/);
  assert.doesNotMatch(analyticsPage, /Advanced analytics is not active on this plan/);
  assert.doesNotMatch(analyticsPage, /FEATURE_CODES\.ADVANCED_ANALYTICS/);
  assert.doesNotMatch(adminDashboard, /FEATURE_CODES\.ADVANCED_ANALYTICS/);
});

test("new tenant admins enter the dashboard tour after initial profile onboarding", () => {
  const onboardingGate = readSource(
    "components",
    "layout",
    "useOnboardingGate.js",
  );

  assert.match(onboardingGate, /postOnboardingRoute\(normalizedRole\)/);
  assert.match(onboardingGate, /profileMode === "onboarding"/);
  assert.match(
    onboardingGate,
    /admin: "\/admin\/dashboard"/,
  );
});

test("linked-school role guides auto-show once with the intended persistence scope", () => {
  const onboardingGate = readSource(
    "components",
    "layout",
    "useOnboardingGate.js",
  );
  const dashboardLayout = readSource("components", "layout", "DashboardLayout.jsx");
  const banner = readSource("components", "guides", "GettingStartedBanner.jsx");
  const guideService = readSource("services", "guideService.js");

  assert.match(onboardingGate, /teacher: "\/teacher\/dashboard"/);
  assert.match(onboardingGate, /parent: "\/parent\/dashboard"/);
  assert.match(onboardingGate, /student: "\/student\/dashboard"/);
  assert.match(onboardingGate, /completedInitialOnboarding/);
  assert.match(dashboardLayout, /hasValidSchoolContext/);
  assert.match(dashboardLayout, /role === "admin" \|\| Boolean\(user\.tenant_id\)/);
  assert.match(guideService, /user\.meta\?\.teacher_account_id/);
  assert.match(guideService, /user\.meta\?\.parent_account_id/);
  assert.match(guideService, /accountScoped\s*\? "global"/);
  assert.match(dashboardLayout, /schoolSetupIncomplete/);
  assert.doesNotMatch(dashboardLayout, /onDismiss=\{dismissGettingStartedBanner\}/);
  assert.match(banner, /Do not show again/);
});

test("admin setup exits directly and completion requires saved foundation evidence", () => {
  const setupRoute = readSource("routes", "AdminGettingStartedRoute.jsx");
  const shell = readSource("components", "layout", "DashboardLayout.jsx");
  assert.match(setupRoute, /schoolYearProgress\(\s*setup\.data\?\.completion,?\s*\)\.complete/);
  assert.match(setupRoute, /await guide\.finish\(\)/);
  assert.match(setupRoute, /leaveGuideRoute\("admin", "\/admin\/dashboard"/);
  assert.doesNotMatch(setupRoute, /document\.addEventListener\("click"/);
  assert.match(shell, /Finish later/);
  assert.doesNotMatch(shell, /shouldAutoRedirect|startRoleGuide/);
});

test("calendar activation confirmation is closed before the lifecycle request runs", () => {
  const calendarSetup = readSource(
    "features",
    "guides",
    "AdminCalendarSetupWorkspace.jsx",
  );

  assert.match(calendarSetup, /activationInFlightRef = useRef\(false\)/);
  assert.match(calendarSetup, /if \(!calendar\?\.id \|\| activationInFlightRef\.current\) return/);
  assert.match(
    calendarSetup,
    /setConfirmActivation\(false\);[\s\S]*await run\(\s*"activate"/,
  );
  assert.match(calendarSetup, /activationInFlightRef\.current = false/);
  assert.match(calendarSetup, /Boolean\(busy\) \|\|\s*confirmActivation/);
});

test("other role introductions offer an explicit tour and return to their dashboard", () => {
  const roleGuide = readSource("pages", "shared", "RoleGettingStartedPage.jsx");
  const shell = readSource("components", "layout", "DashboardLayout.jsx");
  assert.match(roleGuide, /requestWorkspaceTour\(role\)/);
  assert.match(roleGuide, /navigate\(`\/\$\{role\}\/dashboard`, \{ replace: true \}\)/);
  assert.match(shell, /if \(role !== "admin"\)\s*\{?\s*navigate/);
  assert.doesNotMatch(roleGuide, /markComplete|skipCurrent|guide\.start/);
});

test("terminal guide completion must be confirmed before leaving setup", () => {
  const guideService = readSource("services", "guideService.js");
  const setupRoute = readSource("routes", "AdminGettingStartedRoute.jsx");
  assert.match(guideService, /const terminalWrite = TERMINAL_STATUSES\.has\(requestedStatus\)/);
  assert.match(guideService, /ensureTerminalConfirmation\(requestedStatus, response\)/);
  assert.match(guideService, /throw error;/);
  assert.match(setupRoute, /await guide\.finish\(\);\s*leaveGuideRoute/);
  assert.doesNotMatch(setupRoute, /finally\s*\{\s*leaveGuideRoute/);
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
