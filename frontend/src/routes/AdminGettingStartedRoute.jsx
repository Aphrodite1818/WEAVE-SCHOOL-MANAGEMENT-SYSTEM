import { useEffect, useRef } from "react";
import { useParams } from "react-router-dom";

import { leaveGuideRoute } from "../features/guides/guideNavigation";
import useRoleGuide from "../features/guides/useRoleGuide";
import { useAdminSetupReadiness } from "../features/guides/useAdminSetupReadiness";
import { useToast } from "../hooks/useToast";
import AdminGettingStartedPage from "../pages/admin/AdminGettingStartedPage";
import AdminGettingStartedStepPage from "../pages/admin/AdminGettingStartedStepPage";
import { getErrorMessage } from "../services/api";

const normalizeButtonText = (button) =>
  String(button?.textContent || "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
const leaveAdminSetup = (destination) =>
  leaveGuideRoute("admin", destination, { replace: true });

function AdminGettingStartedRoute() {
  const setup = useAdminSetupReadiness();
  const guide = useRoleGuide({
    role: "admin",
    completionMap: setup.loading || setup.error ? null : setup.data?.completion,
  });
  const { finish, moveTo, loading, guideState, steps } = guide;
  const savingStep = useRef(null);
  const { showError } = useToast();
  const { step } = useParams();

  useEffect(() => {
    if (!step || loading || !guideState || savingStep.current === step ||
        ["completed", "dismissed"].includes(guideState.status) ||
        guideState.current_step === step ||
        !steps.some((item) => item.id === step)) return;
    savingStep.current = step;
    moveTo(step)
      .catch((error) => showError(getErrorMessage(error, "Could not save setup progress.")))
      .finally(() => { if (savingStep.current === step) savingStep.current = null; });
  }, [step, loading, guideState, steps, moveTo, showError]);

  useEffect(() => {
    const handleGuideAction = async (event) => {
      const button = event.target?.closest?.("button");
      if (!button || button.disabled) return;
      const label = normalizeButtonText(button);
      if (label === "upgrade plan") {
        event.preventDefault();
        event.stopPropagation();
        leaveAdminSetup("/admin/billing/plans");
        return;
      }
      if (label === "finish later") {
        event.preventDefault();
        event.stopPropagation();
        leaveAdminSetup("/admin/dashboard");
        return;
      }
      if (label === "complete setup" || label === "back to dashboard") {
        event.preventDefault();
        event.stopPropagation();
        if (setup.loading || setup.error || !guide.steps.filter((item) => !item.optional).every((item) => item.complete)) {
          showError("School setup still needs attention. Review the required steps and refresh readiness.");
          return;
        }
        try {
          await finish();
          leaveAdminSetup("/admin/dashboard");
        } catch (error) {
          showError(
            getErrorMessage(
              error,
              "Could not save setup completion. Please try again.",
            ),
          );
        }
      }
    };
    document.addEventListener("click", handleGuideAction, true);
    return () => document.removeEventListener("click", handleGuideAction, true);
  }, [finish, showError, setup.loading, setup.error, guide.steps]);

  return step ? <AdminGettingStartedStepPage /> : <AdminGettingStartedPage setup={setup} guideState={guide} />;
}

export default AdminGettingStartedRoute;
