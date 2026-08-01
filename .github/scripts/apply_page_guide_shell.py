from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8")
    if old not in content:
        raise RuntimeError(f"Expected block not found in {path}: {old[:140]!r}")
    file_path.write_text(content.replace(old, new, 1), encoding="utf-8")


layout = "frontend/src/components/layout/DashboardLayout.jsx"
replace_once(
    layout,
    'import { Outlet, useLocation } from "react-router-dom";\n',
    'import { Outlet, useLocation, useNavigate } from "react-router-dom";\n',
)
replace_once(
    layout,
    'import RoleGuideModal from "../guides/RoleGuideModal";\n',
    'import GettingStartedBanner from "../guides/GettingStartedBanner";\n',
)
replace_once(
    layout,
    '  const location = useLocation();\n  const role = getRole(user, roleProp);\n',
    '  const location = useLocation();\n  const navigate = useNavigate();\n  const role = getRole(user, roleProp);\n',
)
replace_once(
    layout,
    '''  const roleGuide = useRoleGuide({
    role,
    enabled:
      onboardingModalEnabled &&
      !onboardingState.loading &&
      !onboardingState.required &&
      !profileModalOpen,
  });

  useEffect(() => {
''',
    '''  const roleGuide = useRoleGuide({
    role,
    enabled:
      onboardingModalEnabled &&
      !onboardingState.loading &&
      !onboardingState.required &&
      !profileModalOpen,
  });
  const gettingStartedRoute = roleGuide.config?.route || "";
  const showGettingStartedBanner = Boolean(
    roleGuide.shouldShowBanner &&
      roleGuide.config?.dashboardRoute === location.pathname &&
      gettingStartedRoute !== location.pathname,
  );

  useEffect(() => {
    if (
      !roleGuide.shouldAutoRedirect ||
      !gettingStartedRoute ||
      location.pathname === gettingStartedRoute
    ) {
      return undefined;
    }

    let cancelled = false;
    roleGuide.start().then(() => {
      if (!cancelled) navigate(gettingStartedRoute, { replace: true });
    });
    return () => {
      cancelled = true;
    };
  }, [
    gettingStartedRoute,
    location.pathname,
    navigate,
    roleGuide.shouldAutoRedirect,
    roleGuide.start,
  ]);

  useEffect(() => {
''',
)
replace_once(
    layout,
    '''            {children}
          </main>
''',
    '''            {showGettingStartedBanner ? (
              <GettingStartedBanner
                guide={roleGuide}
                onContinue={() => navigate(gettingStartedRoute)}
              />
            ) : null}
            {children}
          </main>
''',
)
replace_once(
    layout,
    '''
      <RoleGuideModal guide={roleGuide} />

      {shouldRenderAiLauncher ? <AiChatLauncher role={role} /> : null}
''',
    '''
      {shouldRenderAiLauncher ? <AiChatLauncher role={role} /> : null}
''',
)

admin_dashboard = "frontend/src/pages/admin/AdminDashboardPage.jsx"
replace_once(
    admin_dashboard,
    'import AdminSetupProgressCard from "../../components/guides/AdminSetupProgressCard";\n',
    '',
)
replace_once(
    admin_dashboard,
    '''          <AdminSetupProgressCard stats={stats} />

''',
    '',
)
