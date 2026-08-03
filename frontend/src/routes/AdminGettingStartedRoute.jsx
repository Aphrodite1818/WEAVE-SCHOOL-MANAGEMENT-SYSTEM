import { useEffect } from "react";

import { leaveGuideRoute } from "../features/guides/guideNavigation";
import useRoleGuide from "../features/guides/useRoleGuide";
import AdminGettingStartedPage from "../pages/admin/AdminGettingStartedPage";

const normalizeButtonText = (button) =>
  String(button?.textContent || "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();

const leaveAdminSetup = (destination) => {
  leaveGuideRoute("admin", destination, { replace: true });
};

/**
 * Handles setup exit actions at the route boundary. Dialogs use portals and
 * the getting-started page has a dedicated full-screen shell, so this capture
 * handler guarantees that exit actions cannot be swallowed by either layer.
 */
function AdminGettingStartedRoute() {
  const guide = useRoleGuide({ role: "admin" });

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
          await guide.finish();
        } finally {
          leaveAdminSetup("/admin/dashboard");
        }
      }
    };

    document.addEventListener("click", handleGuideAction, true);
    return () => document.removeEventListener("click", handleGuideAction, true);
  }, [guide.finish]);

  return <AdminGettingStartedPage />;
}

export default AdminGettingStartedRoute;
