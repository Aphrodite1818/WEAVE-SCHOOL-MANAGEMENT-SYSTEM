import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { onboardingService } from "../../services/onboardingService";

export default function useOnboardingGate({ role, enabled = true }) {
  const navigate = useNavigate();
  const normalizedRole = onboardingService.normalizeRole(role);
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
      if (!enabled || !onboardingService.supportsRole(normalizedRole)) {
        setOnboardingState({ loading: false, required: false, status: null });
        setProfileModalOpen(false);
        return;
      }

      try {
        const status = await onboardingService.getOnboardingStatus(normalizedRole);
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
  }, [normalizedRole, enabled]);

  const handleProfileStateResolved = ({ completed, status }) => {
    const required = !completed;
    setOnboardingState({ loading: false, required, status: status || null });
    if (!required) setProfileModalOpen(false);
  };

  const handleProfileSaved = (status) => {
    const required = Boolean(status?.onboarding_required);
    const completedInitialTenantOnboarding =
      normalizedRole === "admin" && profileMode === "onboarding" && !required;

    setOnboardingState({ loading: false, required, status: status || null });
    if (!required) setProfileModalOpen(false);

    if (completedInitialTenantOnboarding) {
      navigate("/admin/getting-started", { replace: true });
    }
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
