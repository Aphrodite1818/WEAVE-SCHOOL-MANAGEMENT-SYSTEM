import { useEffect } from "react";
import { useParams } from "react-router-dom";

import { leaveGuideRoute } from "../features/guides/guideNavigation";
import useRoleGuide from "../features/guides/useRoleGuide";
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
  const guide = useRoleGuide({ role: "admin" });
  const { finish } = guide;
  const { showError } = useToast();
  const { step } = useParams();

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
  }, [finish, showError]);

  return step ? <AdminGettingStartedStepPage /> : <AdminGettingStartedPage />;
}

export default AdminGettingStartedRoute;
