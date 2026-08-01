from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    if old not in content:
        raise RuntimeError(f"Expected block not found in {path}: {old[:180]!r}")
    write(path, content.replace(old, new, 1))


# ---------------------------------------------------------------------------
# Persist intentional guide exits so a stale not_started response cannot pull
# the actor back into setup after they explicitly leave it.
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/features/guides/guideNavigation.js",
    'const GUIDE_RETURN_STORAGE_KEY = "weave:guide-return";\n',
    '''const GUIDE_RETURN_STORAGE_KEY = "weave:guide-return";
const GUIDE_EXIT_STORAGE_KEY = "weave:guide-exit";
const GUIDE_EXIT_TTL_MS = 5 * 60 * 1000;
''',
)
write(
    "frontend/src/features/guides/guideNavigation.js",
    read("frontend/src/features/guides/guideNavigation.js")
    + '''

export function markGuideExit(role, destination) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(
    GUIDE_EXIT_STORAGE_KEY,
    JSON.stringify({ role, destination, createdAt: Date.now() }),
  );
}

export function hasGuideExitSuppression(role) {
  if (typeof window === "undefined") return false;
  const raw = window.sessionStorage.getItem(GUIDE_EXIT_STORAGE_KEY);
  if (!raw) return false;
  try {
    const parsed = JSON.parse(raw);
    const valid =
      parsed?.role === role &&
      Number.isFinite(parsed?.createdAt) &&
      Date.now() - parsed.createdAt <= GUIDE_EXIT_TTL_MS;
    if (!valid) window.sessionStorage.removeItem(GUIDE_EXIT_STORAGE_KEY);
    return valid;
  } catch {
    window.sessionStorage.removeItem(GUIDE_EXIT_STORAGE_KEY);
    return false;
  }
}

export function leaveGuideRoute(role, destination, { replace = false } = {}) {
  if (typeof window === "undefined") return;
  markGuideExit(role, destination);
  if (replace) window.location.replace(destination);
  else window.location.assign(destination);
}
''',
)

replace_once(
    "frontend/src/features/guides/useRoleGuide.js",
    'import { guideForRole } from "./roleGuideConfig";\n',
    'import { hasGuideExitSuppression } from "./guideNavigation";\nimport { guideForRole } from "./roleGuideConfig";\n',
)
replace_once(
    "frontend/src/features/guides/useRoleGuide.js",
    '''    shouldAutoRedirect:
      enabled && !loading && guideState?.status === "not_started",
''',
    '''    shouldAutoRedirect:
      enabled &&
      !loading &&
      guideState?.status === "not_started" &&
      !hasGuideExitSuppression(role),
''',
)

# ---------------------------------------------------------------------------
# Full-screen guide header: persist an in-progress state before leaving and
# then use a hard route transition so the dashboard always opens.
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    'import { clearGuideReturn, readGuideReturn } from "../../features/guides/guideNavigation";\n',
    '''import {
  clearGuideReturn,
  leaveGuideRoute,
  readGuideReturn,
} from "../../features/guides/guideNavigation";
''',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    '''  const handleLegalRejected = () => {
    setLegalState((current) => ({
      ...current,
      loading: false,
      required: true,
      dismissed: true,
    }));
  };

  if (guidePageActive) {
''',
    '''  const handleLegalRejected = () => {
    setLegalState((current) => ({
      ...current,
      loading: false,
      required: true,
      dismissed: true,
    }));
  };
  const finishGuideLater = async () => {
    const destination = roleGuide.config?.dashboardRoute || `/${role}/dashboard`;
    try {
      if (roleGuide.guideState?.status === "not_started") {
        await roleGuide.start();
      }
    } finally {
      leaveGuideRoute(role, destination, { replace: true });
    }
  };

  if (guidePageActive) {
''',
)
replace_once(
    "frontend/src/components/layout/DashboardLayout.jsx",
    '              onClick={() => navigate(roleGuide.config?.dashboardRoute || `/${role}/dashboard`)}\n',
    '              onClick={finishGuideLater}\n',
)

# ---------------------------------------------------------------------------
# Tenant-admin setup: remove the stale callback stored inside modal state,
# persist guide state before intentional exits, and hard-route all exit paths.
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    'import { useNavigate } from "react-router-dom";\n',
    '',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    'import useRoleGuide from "../../features/guides/useRoleGuide";\n',
    'import { leaveGuideRoute } from "../../features/guides/guideNavigation";\nimport useRoleGuide from "../../features/guides/useRoleGuide";\n',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '  const navigate = useNavigate();\n',
    '',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '''          actionLabel: "Upgrade plan",
          onAction: goToPlanUpgrade,
''',
    '''          actionLabel: "Upgrade plan",
''',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '''      await guide.finish();
      navigate("/admin/dashboard", { replace: true });
''',
    '''      await guide.finish();
      leaveGuideRoute("admin", "/admin/dashboard", { replace: true });
''',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '''  const goPrevious = () => {
    if (!firstStep) guide.moveTo(guide.steps[guide.currentIndex - 1].id);
  };
  const goToPlanUpgrade = () => {
    setWarningDialog(null);
    navigate("/admin/billing/plans");
  };
''',
    '''  const goPrevious = () => {
    if (!firstStep) guide.moveTo(guide.steps[guide.currentIndex - 1].id);
  };
  const persistGuideBeforeExit = async () => {
    if (guide.guideState?.status === "not_started") {
      await guide.start();
      return;
    }
    if (
      guide.guideState?.status !== "completed" &&
      guide.currentStep?.id
    ) {
      await guide.moveTo(guide.currentStep.id);
    }
  };
  const finishLater = async () => {
    try {
      await persistGuideBeforeExit();
    } finally {
      leaveGuideRoute("admin", "/admin/dashboard", { replace: true });
    }
  };
  const goToPlanUpgrade = async () => {
    setWarningDialog(null);
    try {
      await persistGuideBeforeExit();
    } finally {
      leaveGuideRoute("admin", "/admin/billing/plans", { replace: true });
    }
  };
''',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '''    if (guide.guideState?.status === "completed") {
      navigate("/admin/dashboard", { replace: true });
      return;
    }
''',
    '''    if (guide.guideState?.status === "completed") {
      leaveGuideRoute("admin", "/admin/dashboard", { replace: true });
      return;
    }
''',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '''        showSuccess("Assisted setup completed.");
        navigate("/admin/dashboard", { replace: true });
''',
    '''        showSuccess("Assisted setup completed.");
        leaveGuideRoute("admin", "/admin/dashboard", { replace: true });
''',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '    if (lastStep) navigate("/admin/dashboard", { replace: true });\n',
    '    if (lastStep) leaveGuideRoute("admin", "/admin/dashboard", { replace: true });\n',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '                onClick={() => navigate("/admin/dashboard")}\n',
    '                onClick={finishLater}\n',
)
replace_once(
    "frontend/src/pages/admin/AdminGettingStartedPage.jsx",
    '''              {warningDialog?.onAction ? (
                <Button
                  type="button"
                  onClick={() => {
                    const action = warningDialog.onAction;
                    setWarningDialog(null);
                    action();
                  }}
                >
                  <CreditCard className="h-4 w-4" />
                  {warningDialog.actionLabel || "Continue"}
                </Button>
              ) : null}
''',
    '''              {warningDialog?.actionLabel ? (
                <Button type="button" onClick={goToPlanUpgrade}>
                  <CreditCard className="h-4 w-4" />
                  {warningDialog.actionLabel}
                </Button>
              ) : null}
''',
)

# ---------------------------------------------------------------------------
# Teacher/parent/student guide pages: all completion, dismissal and finish
# later exits route through the same reliable mechanism.
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/pages/shared/RoleGettingStartedPage.jsx",
    'import { saveGuideReturn } from "../../features/guides/guideNavigation";\n',
    '''import {
  leaveGuideRoute,
  saveGuideReturn,
} from "../../features/guides/guideNavigation";
''',
)
replace_once(
    "frontend/src/pages/shared/RoleGettingStartedPage.jsx",
    '''  const lastStep = guide.currentIndex >= guide.steps.length - 1;

  const openWorkspace = async () => {
''',
    '''  const lastStep = guide.currentIndex >= guide.steps.length - 1;
  const leaveToDashboard = () =>
    leaveGuideRoute(role, guide.config.dashboardRoute, { replace: true });
  const finishLater = async () => {
    try {
      if (guide.guideState?.status === "not_started") {
        await guide.start();
      } else if (
        guide.guideState?.status !== "completed" &&
        current?.id
      ) {
        await guide.moveTo(current.id);
      }
    } finally {
      leaveToDashboard();
    }
  };

  const openWorkspace = async () => {
''',
)
replace_once(
    "frontend/src/pages/shared/RoleGettingStartedPage.jsx",
    '      navigate(guide.config.dashboardRoute, { replace: true });\n',
    '      leaveToDashboard();\n',
)
replace_once(
    "frontend/src/pages/shared/RoleGettingStartedPage.jsx",
    '    if (lastStep) navigate(guide.config.dashboardRoute, { replace: true });\n',
    '    if (lastStep) leaveToDashboard();\n',
)
replace_once(
    "frontend/src/pages/shared/RoleGettingStartedPage.jsx",
    '''    await guide.dismiss();
    navigate(guide.config.dashboardRoute, { replace: true });
''',
    '''    await guide.dismiss();
    leaveToDashboard();
''',
)
replace_once(
    "frontend/src/pages/shared/RoleGettingStartedPage.jsx",
    '                onClick={() => navigate(guide.config.dashboardRoute)}\n',
    '                onClick={finishLater}\n',
)

# ---------------------------------------------------------------------------
# Regression contracts.
# ---------------------------------------------------------------------------
replace_once(
    "frontend/src/navigationAndGuideContracts.test.js",
    '''test("all guided setup exit actions return to the actor dashboard", () => {
  const adminGuide = readSource("pages", "admin", "AdminGettingStartedPage.jsx");
  const roleGuide = readSource("pages", "shared", "RoleGettingStartedPage.jsx");

  assert.match(adminGuide, /navigate\("\/admin\/dashboard", \{ replace: true \}\)/);
  assert.match(adminGuide, /onClick=\{\(\) => navigate\("\/admin\/dashboard"\)\}/);
  assert.match(roleGuide, /navigate\(guide\.config\.dashboardRoute, \{ replace: true \}\)/);
  assert.match(roleGuide, /onClick=\{\(\) => navigate\(guide\.config\.dashboardRoute\)\}/);
});
''',
    '''test("all guided setup exit actions return to the actor dashboard", () => {
  const shell = readSource("components", "layout", "DashboardLayout.jsx");
  const adminGuide = readSource("pages", "admin", "AdminGettingStartedPage.jsx");
  const roleGuide = readSource("pages", "shared", "RoleGettingStartedPage.jsx");
  const navigation = readSource("features", "guides", "guideNavigation.js");

  assert.match(shell, /onClick=\{finishGuideLater\}/);
  assert.match(adminGuide, /onClick=\{finishLater\}/);
  assert.match(adminGuide, /leaveGuideRoute\("admin", "\/admin\/dashboard"/);
  assert.match(roleGuide, /onClick=\{finishLater\}/);
  assert.match(roleGuide, /leaveGuideRoute\(role, guide\.config\.dashboardRoute/);
  assert.match(navigation, /window\.location\.replace\(destination\)/);
});

test("plan-limit upgrade action leaves setup and opens billing plans", () => {
  const adminGuide = readSource("pages", "admin", "AdminGettingStartedPage.jsx");

  assert.match(adminGuide, /onClick=\{goToPlanUpgrade\}/);
  assert.match(
    adminGuide,
    /leaveGuideRoute\("admin", "\/admin\/billing\/plans", \{ replace: true \}\)/,
  );
  assert.doesNotMatch(adminGuide, /warningDialog\.onAction/);
});
''',
)

print("Applied guide exit navigation fixes.")
