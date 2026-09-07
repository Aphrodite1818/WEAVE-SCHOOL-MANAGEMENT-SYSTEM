import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { onboardingService } from "../../services/onboardingService";
import { guideService } from "../../services/guideService";
import { queueInitialTour } from "../../features/guides/workspaceTourState";

const GETTING_STARTED_ROUTE_BY_ROLE = {
  admin: "/admin/dashboard",
  teacher: "/teacher/dashboard",
  parent: "/parent/dashboard",
  student: "/student/dashboard",
};

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
        await queueInitialTour(normalizedRole, completedInitialOnboarding, guideService);
      } catch {
        // An unavailable tour must not block a successfully saved profile.
      } finally {
        setPreparingWelcome(false);
      }
    }

    setOnboardingState({ loading: false, required, status: status || null });
    if (!required) setProfileModalOpen(false);

    if (
      completedInitialOnboarding &&
      GETTING_STARTED_ROUTE_BY_ROLE[normalizedRole]
    ) {
      navigate(GETTING_STARTED_ROUTE_BY_ROLE[normalizedRole], {
        replace: true,
      });
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
