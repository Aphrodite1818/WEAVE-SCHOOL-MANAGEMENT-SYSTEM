import { useEffect, useState } from "react";

import { onboardingService } from "../../services/onboardingService";

export default function useOnboardingGate({ role, enabled = true }) {
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [profileMode, setProfileMode] = useState("onboarding");
  const [onboardingState, setOnboardingState] = useState({
    loading: true,
    required: false,
    status: null,
  });

  useEffect(() => {
    let mounted = true;

    async function checkOnboarding() {
      if (!enabled || !onboardingService.supportsRole(role)) {
        setOnboardingState({ loading: false, required: false, status: null });
        setProfileModalOpen(false);
        return;
      }

      try {
        const status = await onboardingService.getOnboardingStatus(role);
        if (!mounted) return;

        const required = Boolean(status?.onboarding_required);
        setOnboardingState({ loading: false, required, status: status || null });

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
  }, [role, enabled]);

  const handleProfileStateResolved = ({ completed, status }) => {
    const required = !completed;
    setOnboardingState({ loading: false, required, status: status || null });
    if (!required) setProfileModalOpen(false);
  };

  const handleProfileSaved = (status) => {
    const required = Boolean(status?.onboarding_required);
    setOnboardingState({ loading: false, required, status: status || null });
    if (!required) setProfileModalOpen(false);
  };

  return {
    onboardingState,
    profileModalOpen,
    setProfileModalOpen,
    profileMode,
    setProfileMode,
    handleProfileStateResolved,
    handleProfileSaved,
  };
}
