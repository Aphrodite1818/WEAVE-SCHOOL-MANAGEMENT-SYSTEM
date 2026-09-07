import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { queueInitialTour } from "../../features/guides/workspaceTourState";
import { authSession } from "../../services/api";
import { guideService } from "../../services/guideService";
import { onboardingService } from "../../services/onboardingService";

const DASHBOARD_ROUTE_BY_ROLE = {
  admin: "/admin/dashboard",
  teacher: "/teacher/dashboard",
  parent: "/parent/dashboard",
  student: "/student/dashboard",
};

const SCHOOL_SELECTION_ROUTE_BY_ROLE = {
  teacher: "/teacher/schools",
  parent: "/parent/schools",
};

function postOnboardingRoute(role) {
  const user = authSession.getUser() || {};
  const actorType = String(user.actor_type || user.account_type || "").toLowerCase();
  const accountScoped =
    ["teacher_account", "parent_account"].includes(actorType) && !user.tenant_id;

  if (accountScoped && SCHOOL_SELECTION_ROUTE_BY_ROLE[role]) {
    return SCHOOL_SELECTION_ROUTE_BY_ROLE[role];
  }
  return DASHBOARD_ROUTE_BY_ROLE[role] || null;
}

export default function useOnboardingGate({ role, enabled = true }) {
  const navigate = useNavigate();
  const normalizedRole = onboardingService.normalizeRole(role);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [profileMode, setProfileMode] = useState("onboarding");
  const [preparingWelcome, setPreparingWelcome] = useState(false);
  const [onboardingState, setOnboardingState] = useState({
    loading: true,
    required: false,
    status: null,
  });

  useEffect(() => {
    let mounted = true;

    async function checkOnboarding() {
      if (!enabled || !onboardingService.supportsRole(normalizedRole)) {
        setOnboardingState({ loading: false, required: false, status: null });
        setProfileModalOpen(false);
        return;
      }

      try {
        const status =
          await onboardingService.getOnboardingStatus(normalizedRole);
        if (!mounted) return;

        const required = Boolean(status?.onboarding_required);
        setOnboardingState({
          loading: false,
          required,
          status: status || null,
        });

        if (required) {
          setProfileMode("onboarding");
          setProfileModalOpen(true);
        }
      } catch {
        if (mounted) {
          setOnboardingState((current) => ({ ...current, loading: false }));
        }
      }
    }

    checkOnboarding();

    return () => {
      mounted = false;
    };
  }, [normalizedRole, enabled]);

  const handleProfileStateResolved = ({ completed, status }) => {
    const required = !completed;
    setOnboardingState({ loading: false, required, status: status || null });
    if (!required) setProfileModalOpen(false);
  };

  const handleProfileSaved = async (status) => {
    const required = Boolean(status?.onboarding_required);
    const completedInitialOnboarding =
      profileMode === "onboarding" && onboardingState.required && !required;

    if (completedInitialOnboarding) {
      setPreparingWelcome(true);
      try {
        await queueInitialTour(
          normalizedRole,
          completedInitialOnboarding,
          guideService,
        );
      } catch {
        // An unavailable tour must not block a successfully saved profile.
      } finally {
        setPreparingWelcome(false);
      }
    }

    setOnboardingState({ loading: false, required, status: status || null });
    if (!required) setProfileModalOpen(false);

    if (completedInitialOnboarding) {
      const nextRoute = postOnboardingRoute(normalizedRole);
      if (nextRoute) {
        navigate(nextRoute, { replace: true });
      }
    }
  };

  return {
    preparingWelcome,
    onboardingState,
    profileModalOpen,
    setProfileModalOpen,
    profileMode,
    setProfileMode,
    handleProfileStateResolved,
    handleProfileSaved,
  };
}
