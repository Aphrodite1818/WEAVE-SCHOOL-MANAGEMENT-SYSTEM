import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ArrowLeft, X } from "lucide-react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { clearGuideReturn, readGuideReturn } from "../../features/guides/guideNavigation";
import { FEATURE_CODES } from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { TenantBrandingProvider } from "../../features/tenant-branding/TenantBrandingProvider";
import { useTenantBranding } from "../../features/tenant-branding/useTenantBranding";
import LegalComplianceModal from "../../features/legal/LegalComplianceModal";
import { authSession } from "../../services/api";
import { clearDashboardSessionCache } from "../../services/dashboardSessionCache";
import { legalComplianceService } from "../../services/legalComplianceService";
import { cn } from "../../utils/cn";
import { scrollDashboardViewportToTop } from "../../utils/dashboardScroll";
import { scheduleThemeChromeSync } from "../../utils/themeChromeSync";
import AiChatLauncher from "../ai/AiChatLauncher";
import WeaveIcon from "../brand/WeaveIcon";
import ProfileCompletionForm from "../shared/ProfileCompletionForm";
import GettingStartedBanner from "../guides/GettingStartedBanner";
import Button from "../ui/Button";
import Modal from "../ui/Modal";
import BottomNav from "./BottomNav";
import MobileDrawer from "./MobileDrawer";
import SidebarContent from "./Sidebar";
import Topbar from "./Topbar";
import { onboardingModalCopy } from "./navConfig";
import useOnboardingGate from "./useOnboardingGate";
import useRoleGuide from "../../features/guides/useRoleGuide";

const DashboardShellContext = createContext(null);
const PULL_REFRESH_THRESHOLD = 68;
const DRAWER_OPEN_DISTANCE = 72;
const DRAWER_VERTICAL_TOLERANCE = 70;
const DRAWER_CENTER_START_MIN = 0.28;
const DRAWER_CENTER_START_MAX = 0.72;
const GESTURE_ACTIVATION_DISTANCE = 12;
const AI_CHAT_LAUNCHER_VISIBLE = false;

function getDefaultPageMeta(role, onboardingModalEnabled = true) {
  return {
    role,
    title: null,
    description: null,
    actions: null,
    onboardingModalEnabled,
  };
}

function getRole(user, fallback) {
  return String(user?.role || authSession.getRole() || fallback || "admin").toLowerCase();
}

function isMobileViewport() {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(max-width: 767px)").matches;
}

function isCenterDrawerGestureStart(clientX) {
  if (typeof window === "undefined") return false;
  const width = window.innerWidth || 0;
  if (!width) return false;
  return clientX >= width * DRAWER_CENTER_START_MIN && clientX <= width * DRAWER_CENTER_START_MAX;
}

function blocksDrawerGesture(target) {
  if (!target || typeof target.closest !== "function") return false;
  return Boolean(
    target.closest(
      "button, a, input, select, textarea, [role='button'], [data-mobile-drawer='true'], .chart-interactive-scroll"
    )
  );
}

function DashboardShellFrame({
  role: roleProp = "admin",
  title,
  description,
  actions,
  children,
  onboardingModalEnabled = true,
}) {
  const user = useMemo(() => authSession.getUser() || {}, []);
  const location = useLocation();
  const navigate = useNavigate();
  const role = getRole(user, roleProp);
  const guidePageActive = location.pathname.endsWith("/getting-started");
  const academicHubActive = location.pathname.startsWith("/admin/academic");
  const {
    entitlements,
    getFeatureGuard,
    isTenantAdmin,
  } = useSubscription();
  const [legalState, setLegalState] = useState(() => ({
    loading: onboardingModalEnabled,
    required: Boolean(user?.legal_compliance_required ?? onboardingModalEnabled),
    dismissed: false,
    status: null,
  }));
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [guideReturn, setGuideReturn] = useState(() => readGuideReturn());
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() =>
    window.localStorage.getItem("sidebarCollapsed") === "true"
  );
  const [pullDistance, setPullDistance] = useState(0);
  const [drawerSwipeDistance, setDrawerSwipeDistance] = useState(0);
  const [isPullRefreshing, setIsPullRefreshing] = useState(false);
  const shellRef = useRef(null);
  const mainRef = useRef(null);
  const pullStateRef = useRef({ tracking: false, active: false, startX: 0, startY: 0 });
  const drawerSwipeRef = useRef({
    tracking: false,
    active: false,
    startX: 0,
    startY: 0,
    currentX: 0,
    currentY: 0,
  });
  const workspaceBranding = useTenantBranding();
  const schoolName = workspaceBranding.schoolName;
  const aiAssistantGuard =
    role === "admin" && isTenantAdmin
      ? getFeatureGuard(FEATURE_CODES.AI_ASSISTANT || "ai_assistant")
      : { allowed: true, pending: false };
  const showAiLauncher =
    role !== "admin" || !isTenantAdmin ? true : Boolean(entitlements) && aiAssistantGuard.allowed;
  const shouldRenderAiLauncher = AI_CHAT_LAUNCHER_VISIBLE && showAiLauncher;
  const legalBlocksProgression = Boolean(legalState.loading || legalState.required);
  const {
    onboardingState,
    profileModalOpen,
    setProfileModalOpen,
    profileMode,
    handleProfileStateResolved,
    handleProfileSaved,
  } = useOnboardingGate({
    role,
    enabled: onboardingModalEnabled && !legalBlocksProgression,
  });
  const roleGuide = useRoleGuide({
    role,
    enabled:
      onboardingModalEnabled &&
      !legalBlocksProgression &&
      !onboardingState.loading &&
      !onboardingState.required &&
      !profileModalOpen,
  });
  const gettingStartedRoute = roleGuide.config?.route || "";
  const startRoleGuide = roleGuide.start;
  const shouldAutoRedirect = roleGuide.shouldAutoRedirect;
  const showGettingStartedBanner = Boolean(
    roleGuide.shouldShowBanner &&
      roleGuide.config?.dashboardRoute === location.pathname &&
      gettingStartedRoute !== location.pathname,
  );

  useEffect(() => {
    let cancelled = false;

    async function loadLegalStatus() {
      if (!onboardingModalEnabled) {
        setLegalState({ loading: false, required: false, dismissed: false, status: null });
        return;
      }

      setLegalState((current) => ({ ...current, loading: true }));
      try {
        const status = await legalComplianceService.getStatus();
        if (cancelled) return;
        setLegalState({
          loading: false,
          required: !status?.accepted,
          dismissed: false,
          status: status || null,
        });
      } catch {
        if (!cancelled) {
          setLegalState((current) => ({ ...current, loading: false }));
        }
      }
    }

    loadLegalStatus();

    return () => {
      cancelled = true;
    };
  }, [onboardingModalEnabled, role]);

  useEffect(() => {
    if (legalState.required) setProfileModalOpen(false);
  }, [legalState.required, setProfileModalOpen]);

  useEffect(() => {
    if (
      !shouldAutoRedirect ||
      !gettingStartedRoute ||
      location.pathname === gettingStartedRoute
    ) {
      return undefined;
    }

    let cancelled = false;
    startRoleGuide().then(() => {
      if (!cancelled) navigate(gettingStartedRoute, { replace: true });
    });
    return () => {
      cancelled = true;
    };
  }, [
    gettingStartedRoute,
    location.pathname,
    navigate,
    shouldAutoRedirect,
    startRoleGuide,
  ]);

  useEffect(() => {
    window.localStorage.setItem("sidebarCollapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  useEffect(() => {
    if (guidePageActive) {
      clearGuideReturn();
      setGuideReturn(null);
      return;
    }
    setGuideReturn(readGuideReturn());
  }, [guidePageActive, location.pathname]);

  useEffect(() => {
    if (!academicHubActive) return;
    setSidebarCollapsed(true);
    setMobileNavOpen(false);
  }, [academicHubActive, location.pathname]);

  useEffect(() => {
    scrollDashboardViewportToTop("auto");
  }, [location.pathname]);


  useEffect(() => {
    scheduleThemeChromeSync();
    window.addEventListener("pageshow", scheduleThemeChromeSync);
    return () => {
      window.removeEventListener("pageshow", scheduleThemeChromeSync);
    };
  }, [role]);

  const handleTouchStart = useCallback((event) => {
    if (!isMobileViewport()) return;

    const touch = event.touches?.[0];
    if (!touch) return;

    drawerSwipeRef.current = {
      tracking: false,
      active: false,
      startX: 0,
      startY: 0,
      currentX: 0,
      currentY: 0,
    };
    pullStateRef.current = { tracking: false, active: false, startX: 0, startY: 0 };

    const canOpenDrawer =
      !mobileNavOpen &&
      isCenterDrawerGestureStart(touch.clientX) &&
      !blocksDrawerGesture(event.target);
    const canPullRefresh =
      !isPullRefreshing && (mainRef.current?.scrollTop || 0) <= 0;

    if (canOpenDrawer) {
      drawerSwipeRef.current = {
        tracking: true,
        active: false,
        startX: touch.clientX,
        startY: touch.clientY,
        currentX: touch.clientX,
        currentY: touch.clientY,
      };
      setPullDistance(0);
    }

    if (canPullRefresh) {
      pullStateRef.current = {
        tracking: true,
        active: false,
        startX: touch.clientX,
        startY: touch.clientY,
      };
    }
  }, [isPullRefreshing, mobileNavOpen]);

  const handleTouchMove = useCallback((event) => {
    if (!isMobileViewport()) return;

    const touch = event.touches?.[0];
    if (!touch) return;

    const drawerState = drawerSwipeRef.current;
    if (drawerState.tracking) {
      const rawDeltaX = touch.clientX - drawerState.startX;
      const deltaX = Math.abs(rawDeltaX);
      const deltaY = touch.clientY - drawerState.startY;
      const absDeltaY = Math.abs(deltaY);
      const shouldActivateDrawer =
        drawerState.active ||
        (deltaX >= GESTURE_ACTIVATION_DISTANCE &&
          deltaX > absDeltaY + 4);

      drawerSwipeRef.current = {
        ...drawerState,
        active: shouldActivateDrawer,
        currentX: touch.clientX,
        currentY: touch.clientY,
      };

      if (shouldActivateDrawer) {
        event.preventDefault();
        setDrawerSwipeDistance(Math.min(96, Math.round(deltaX * 0.62)));
        pullStateRef.current = { tracking: false, active: false, startX: 0, startY: 0 };
        return;
      }

      if (absDeltaY >= GESTURE_ACTIVATION_DISTANCE && absDeltaY > deltaX + 4) {
        drawerSwipeRef.current = {
          tracking: false,
          active: false,
          startX: 0,
          startY: 0,
          currentX: 0,
          currentY: 0,
        };
      }
    }

    const state = pullStateRef.current;
    if (!state.tracking || isPullRefreshing) return;

    if ((mainRef.current?.scrollTop || 0) > 0) {
      pullStateRef.current = { tracking: false, startY: 0 };
      setPullDistance(0);
      return;
    }

    const deltaX = Math.abs(touch.clientX - state.startX);
    const deltaY = touch.clientY - state.startY;
    if (deltaY <= 0) {
      setPullDistance(0);
      return;
    }

    const shouldActivatePull =
      state.active ||
      (deltaY >= GESTURE_ACTIVATION_DISTANCE &&
        deltaY > deltaX + 4);

    if (!shouldActivatePull) return;

    pullStateRef.current = { ...state, active: true };
    if (deltaY > 8) event.preventDefault();
    setPullDistance(Math.min(104, Math.round(deltaY * 0.46)));
  }, [isPullRefreshing]);

  const handleTouchEnd = useCallback(() => {
    const drawerState = drawerSwipeRef.current;
    if (drawerState.tracking) {
      const deltaX = Math.abs(drawerState.currentX - drawerState.startX);
      const deltaY = drawerState.currentY - drawerState.startY;
      const shouldOpenDrawer =
        drawerState.active &&
        deltaX >= DRAWER_OPEN_DISTANCE &&
        Math.abs(deltaY) <= DRAWER_VERTICAL_TOLERANCE;

      drawerSwipeRef.current = {
        tracking: false,
        active: false,
        startX: 0,
        startY: 0,
        currentX: 0,
        currentY: 0,
      };
      setDrawerSwipeDistance(0);

      if (shouldOpenDrawer) setMobileNavOpen(true);
      return;
    }

    const shouldRefresh = pullDistance >= PULL_REFRESH_THRESHOLD;
    pullStateRef.current = { tracking: false, active: false, startX: 0, startY: 0 };

    if (!shouldRefresh) {
      setPullDistance(0);
      return;
    }

    setIsPullRefreshing(true);
    setPullDistance(PULL_REFRESH_THRESHOLD);
    clearDashboardSessionCache();
    window.dispatchEvent(
      new CustomEvent("weave:pull-refresh", {
        detail: { requestedAt: Date.now() },
      }),
    );
    window.setTimeout(() => {
      setIsPullRefreshing(false);
      setPullDistance(0);
    }, 1200);
  }, [pullDistance]);

  const handleTouchCancel = useCallback(() => {
    pullStateRef.current = { tracking: false, active: false, startX: 0, startY: 0 };
    drawerSwipeRef.current = {
      tracking: false,
      active: false,
      startX: 0,
      startY: 0,
      currentX: 0,
      currentY: 0,
    };
    setPullDistance(0);
    setDrawerSwipeDistance(0);
  }, []);

  const profileCopy = onboardingModalCopy[role] || onboardingModalCopy.teacher;
  const pullRefreshLabel = isPullRefreshing
    ? "Refreshing..."
    : pullDistance >= PULL_REFRESH_THRESHOLD
      ? "Release to refresh"
      : "Pull to refresh";

  const returnToGuide = () => {
    const route = guideReturn?.route;
    clearGuideReturn();
    setGuideReturn(null);
    if (route) navigate(route);
  };
  const dismissGuideReturn = () => {
    clearGuideReturn();
    setGuideReturn(null);
  };
  const handleLegalAccepted = (status) => {
    setLegalState({
      loading: false,
      required: false,
      dismissed: false,
      status: status || null,
    });
  };
  const handleLegalRejected = () => {
    setLegalState((current) => ({
      ...current,
      loading: false,
      required: true,
      dismissed: true,
    }));
  };

  if (guidePageActive) {
    return (
      <div
        ref={shellRef}
        data-dashboard-role={role}
        data-guide-page="true"
        className="min-h-[100dvh] overflow-y-auto bg-background text-text"
      >
        <header className="sticky top-0 z-40 border-b border-border/70 bg-surface/95 backdrop-blur-xl">
          <div className="mx-auto flex min-h-16 w-full max-w-[1440px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
            <div className="flex items-center gap-3">
              <WeaveIcon className="h-10 w-10 shrink-0" decorative />
              <div>
                <p className="text-sm font-bold text-text">Weave</p>
                <p className="text-xs text-text-muted">Getting started</p>
              </div>
            </div>
            <Button
              type="button"
              size="small"
              variant="outline"
              onClick={() => navigate(roleGuide.config?.dashboardRoute || `/${role}/dashboard`)}
            >
              Finish later
            </Button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1440px] px-3 py-5 sm:px-6 sm:py-7 lg:px-8 lg:py-9">
          {children}
        </main>
      </div>
    );
  }

  return (
    <div
      ref={shellRef}
      data-dashboard-role={role}
      className="fixed inset-0 flex min-h-[100dvh] flex-col overflow-hidden bg-background text-text"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-x-0 top-0 z-[70] hidden bg-surface md:hidden"
        data-pwa-status-fill="true"
        style={{ height: "env(safe-area-inset-top)" }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-30 hidden bg-background md:hidden"
        data-pwa-safe-area-fill="true"
        style={{ height: "calc(env(safe-area-inset-bottom) + 1rem)" }}
      />
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden border-r border-sidebar-border bg-sidebar-background text-sidebar-text transition-all duration-300 md:block",
          sidebarCollapsed ? "w-[4.25rem]" : "w-[13rem] xl:w-[14rem]"
        )}
      >
        <SidebarContent
          role={role}
          collapsed={sidebarCollapsed}
          schoolName={schoolName}
          schoolLogoUrl={workspaceBranding.logoUrl}
          onToggleSidebar={() => setSidebarCollapsed((value) => !value)}
        />
      </aside>

      <MobileDrawer
        open={mobileNavOpen}
        role={role}
        schoolName={schoolName}
        schoolLogoUrl={workspaceBranding.logoUrl}
        onClose={() => setMobileNavOpen(false)}
      />

      <div
        className={cn(
          "flex h-full min-h-0 flex-col overflow-hidden transition-[padding] duration-300",
          sidebarCollapsed ? "md:pl-[4.25rem]" : "md:pl-[13rem] xl:pl-[14rem]"
        )}
      >
        <Topbar
          role={role}
          onOpenMobileNav={() => setMobileNavOpen(true)}
          schoolName={schoolName}
          schoolLogoUrl={workspaceBranding.logoUrl}
        />
        <div
          id="dashboard-scroll-viewport"
          ref={mainRef}
          className="relative min-h-0 flex-1 overflow-y-auto overscroll-contain"
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
          onTouchCancel={handleTouchCancel}
        >
          <div
            aria-hidden="true"
            className="pointer-events-none fixed left-1/2 top-1/2 z-30 hidden -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/80 transition-[width,opacity] duration-150 md:hidden"
            style={{ width: drawerSwipeDistance ? `${Math.max(8, drawerSwipeDistance / 2)}px` : 0, height: drawerSwipeDistance ? "0.35rem" : 0, opacity: drawerSwipeDistance ? 1 : 0 }}
          />
          <div
            className="pointer-events-none sticky top-0 z-20 flex justify-center overflow-hidden transition-[height,opacity] duration-150 md:hidden"
            style={{ height: pullDistance ? `${pullDistance}px` : 0, opacity: pullDistance ? 1 : 0 }}
          >
            <div className="mt-2 inline-flex h-10 items-center rounded-full border border-border bg-surface/95 px-4 text-xs font-semibold text-text-muted shadow-lg backdrop-blur-md">
              {pullRefreshLabel}
            </div>
          </div>
          <main
            id="dashboard-content"
            className={cn(
              "mx-auto flex w-full max-w-[1320px] flex-col gap-5 px-3 pt-4 sm:gap-6 sm:px-5 sm:pt-6 lg:px-8",
              shouldRenderAiLauncher ? "pb-10 sm:pb-24 lg:pb-28" : "pb-6 sm:pb-12"
            )}
          >
            {(title || description || actions) && (
              <section className="page-header">
                <div className="min-w-0 flex-1">
                  {title ? <h1 className="page-title">{title}</h1> : null}
                  {description ? (
                    <p className="mt-1 max-w-3xl text-sm leading-6 text-text-muted">{description}</p>
                  ) : null}
                </div>
                {actions ? (
                  <div className="page-header-actions flex w-full justify-start md:w-auto md:max-w-full md:justify-end">
                    {actions}
                  </div>
                ) : null}
              </section>
            )}
            {guideReturn?.role === role ? (
              <section className="flex flex-col gap-3 rounded-2xl border border-primary/25 bg-primary-subtle/70 px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                    <ArrowLeft className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-text">Tutorial still in progress</p>
                    <p className="truncate text-xs text-text-muted">
                      {guideReturn.label || "Return to the getting-started page when you are done exploring."}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button type="button" size="small" onClick={returnToGuide}>
                    Return to tutorial
                  </Button>
                  <button
                    type="button"
                    onClick={dismissGuideReturn}
                    className="grid h-9 w-9 place-items-center rounded-xl text-text-muted transition hover:bg-surface hover:text-text"
                    aria-label="Dismiss tutorial return prompt"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </section>
            ) : null}
            {showGettingStartedBanner ? (
              <GettingStartedBanner
                guide={roleGuide}
                onContinue={() => navigate(gettingStartedRoute)}
              />
            ) : null}
            {children}
          </main>
        </div>
      </div>

      <BottomNav role={role} onOpenMenu={() => setMobileNavOpen(true)} />

      {onboardingModalEnabled ? (
        <LegalComplianceModal
          open={Boolean(legalState.required && !legalState.dismissed)}
          role={role}
          onAccepted={handleLegalAccepted}
          onRejected={handleLegalRejected}
        />
      ) : null}

      {onboardingModalEnabled ? (
        <Modal
          open={profileModalOpen}
          onClose={() => !onboardingState.required && setProfileModalOpen(false)}
          title={profileMode === "onboarding" ? profileCopy.onboardingTitle : profileCopy.editTitle}
          description={profileMode === "onboarding" ? null : profileCopy.editDescription}
          closeOnOverlay={!onboardingState.required}
          showClose={!onboardingState.required}
        >
          <ProfileCompletionForm
            role={role}
            mode={profileMode}
            initialStatusData={onboardingState.status}
            onProfileStateResolved={handleProfileStateResolved}
            onSaved={handleProfileSaved}
          />
        </Modal>
      ) : null}

      {shouldRenderAiLauncher ? <AiChatLauncher role={role} /> : null}
    </div>
  );
}

export function DashboardShell({ role = "admin", onboardingModalEnabled = true }) {
  const location = useLocation();
  const [pageMeta, setPageMetaState] = useState(() =>
    getDefaultPageMeta(role, onboardingModalEnabled)
  );

  useEffect(() => {
    setPageMetaState(getDefaultPageMeta(role, onboardingModalEnabled));
  }, [location.pathname, role, onboardingModalEnabled]);

  const setPageMeta = useCallback(
    (meta) => {
      setPageMetaState((current) => {
        const next = {
          role: meta.role || role,
          title: meta.title || null,
          description: meta.description || null,
          actions: meta.actions || null,
          onboardingModalEnabled:
            meta.onboardingModalEnabled ?? onboardingModalEnabled,
        };

        if (
          current.role === next.role &&
          current.title === next.title &&
          current.description === next.description &&
          current.actions === next.actions &&
          current.onboardingModalEnabled === next.onboardingModalEnabled
        ) {
          return current;
        }

        return next;
      });
    },
    [onboardingModalEnabled, role]
  );

  const shellContext = useMemo(() => ({ setPageMeta }), [setPageMeta]);

  return (
    <TenantBrandingProvider user={authSession.getUser() || {}} role={pageMeta.role}>
      <DashboardShellContext.Provider value={shellContext}>
        <DashboardShellFrame {...pageMeta}>
          <Outlet />
        </DashboardShellFrame>
      </DashboardShellContext.Provider>
    </TenantBrandingProvider>
  );
}

function DashboardLayout({
  role: roleProp = "admin",
  title,
  description,
  actions,
  children,
  onboardingModalEnabled = true,
}) {
  const shell = useContext(DashboardShellContext);
  const location = useLocation();

  useEffect(() => {
    if (!shell) return;

    shell.setPageMeta({
      role: roleProp,
      title,
      description,
      actions,
      onboardingModalEnabled,
    });
  }, [shell, location.pathname, roleProp, title, description, actions, onboardingModalEnabled]);

  if (shell) return <>{children}</>;

  return (
    <TenantBrandingProvider user={authSession.getUser() || {}} role={roleProp}>
      <DashboardShellFrame
        role={roleProp}
        title={title}
        description={description}
        actions={actions}
        onboardingModalEnabled={onboardingModalEnabled}
      >
        {children}
      </DashboardShellFrame>
    </TenantBrandingProvider>
  );
}

export default DashboardLayout;
