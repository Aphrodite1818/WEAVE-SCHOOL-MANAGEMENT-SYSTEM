import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Outlet, useLocation } from "react-router-dom";

import { FEATURE_CODES } from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { authSession } from "../../services/api";
import { cn } from "../../utils/cn";
import { scrollDashboardViewportToTop } from "../../utils/dashboardScroll";
import AiChatLauncher from "../ai/AiChatLauncher";
import ProfileCompletionForm from "../shared/ProfileCompletionForm";
import Modal from "../ui/Modal";
import BottomNav from "./BottomNav";
import MobileDrawer from "./MobileDrawer";
import SidebarContent from "./Sidebar";
import Topbar from "./Topbar";
import { onboardingModalCopy } from "./navConfig";
import useOnboardingGate from "./useOnboardingGate";
import useTenantWorkspaceName from "./useTenantWorkspaceName";

const DashboardShellContext = createContext(null);

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

function DashboardShellFrame({
  role: roleProp = "admin",
  title,
  description,
  actions,
  children,
  onboardingModalEnabled = true,
}) {
  const user = authSession.getUser() || {};
  const location = useLocation();
  const role = getRole(user, roleProp);
  const { entitlements, getFeatureGuard, isTenantAdmin } = useSubscription();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() =>
    window.localStorage.getItem("sidebarCollapsed") === "true"
  );
  const mainRef = useRef(null);
  const schoolName = useTenantWorkspaceName({ user, role });
  const aiAssistantGuard =
    role === "admin" && isTenantAdmin
      ? getFeatureGuard(FEATURE_CODES.AI_ASSISTANT || "ai_assistant")
      : { allowed: true, pending: false };
  const showAiLauncher =
    role !== "admin" || !isTenantAdmin ? true : Boolean(entitlements) && aiAssistantGuard.allowed;
  const {
    onboardingState,
    profileModalOpen,
    setProfileModalOpen,
    profileMode,
    handleProfileStateResolved,
    handleProfileSaved,
  } = useOnboardingGate({ role, enabled: onboardingModalEnabled });

  useEffect(() => {
    window.localStorage.setItem("sidebarCollapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  useEffect(() => {
    scrollDashboardViewportToTop("auto");
  }, [location.pathname]);

  const profileCopy = onboardingModalCopy[role] || onboardingModalCopy.teacher;

  return (
    <div className="flex h-screen h-[100dvh] flex-col overflow-hidden bg-background text-text">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden border-r border-border bg-surface transition-all duration-300 md:block",
          sidebarCollapsed ? "w-[4.25rem]" : "w-[15rem]"
        )}
      >
        <SidebarContent
          role={role}
          collapsed={sidebarCollapsed}
          onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
          schoolName={schoolName}
        />
      </aside>

      <MobileDrawer
        open={mobileNavOpen}
        role={role}
        schoolName={schoolName}
        onClose={() => setMobileNavOpen(false)}
      />

      <div
        className={cn(
          "flex h-full min-h-0 flex-col overflow-hidden transition-[padding] duration-300",
          sidebarCollapsed ? "md:pl-[4.25rem]" : "md:pl-[15rem]"
        )}
      >
        <Topbar role={role} onOpenMobileNav={() => setMobileNavOpen(true)} schoolName={schoolName} />
        <div
          id="dashboard-scroll-viewport"
          ref={mainRef}
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain"
        >
          <main
            id="dashboard-content"
            className={cn(
              "mx-auto flex w-full max-w-[1320px] flex-col gap-5 px-3 pt-4 sm:gap-6 sm:px-5 sm:pt-6 lg:px-8",
              showAiLauncher ? "pb-36 sm:pb-24 lg:pb-28" : "pb-28 sm:pb-12"
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
                  <div className="flex w-full justify-start md:w-auto md:max-w-full md:justify-end">
                    {actions}
                  </div>
                ) : null}
              </section>
            )}
            {children}
          </main>
        </div>
      </div>

      <BottomNav role={role} onOpenMenu={() => setMobileNavOpen(true)} />

      {onboardingModalEnabled ? (
        <Modal
          open={profileModalOpen}
          onClose={() => !onboardingState.required && setProfileModalOpen(false)}
          title={profileMode === "onboarding" ? profileCopy.onboardingTitle : profileCopy.editTitle}
          description={profileMode === "onboarding" ? profileCopy.onboardingDescription : profileCopy.editDescription}
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

      {showAiLauncher ? <AiChatLauncher role={role} /> : null}
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
    <DashboardShellContext.Provider value={shellContext}>
      <DashboardShellFrame {...pageMeta}>
        <Outlet />
      </DashboardShellFrame>
    </DashboardShellContext.Provider>
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
    <DashboardShellFrame
      role={roleProp}
      title={title}
      description={description}
      actions={actions}
      onboardingModalEnabled={onboardingModalEnabled}
    >
      {children}
    </DashboardShellFrame>
  );
}

export default DashboardLayout;
