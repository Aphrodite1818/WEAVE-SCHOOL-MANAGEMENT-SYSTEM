import { useEffect } from "react";

import AdminGettingStartedPage from "../pages/admin/AdminGettingStartedPage";
import useRoleGuide from "../features/guides/useRoleGuide";

const normalizeButtonText = (button) =>
  String(button?.textContent || "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();

const hardNavigate = (path) => {
  window.location.assign(path);
};

/**
 * Keeps the assisted setup actions reliable even though dialogs are rendered
 * through portals and the getting-started page uses a dedicated full-screen shell.
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
        hardNavigate("/admin/billing/plans");
        return;
      }

      if (label === "finish later") {
        event.preventDefault();
        event.stopPropagation();
        hardNavigate("/admin/dashboard");
        return;
      }

      if (label === "complete setup" || label === "back to dashboard") {
        event.preventDefault();
        event.stopPropagation();
        try {
          await guide.finish();
        } finally {
          hardNavigate("/admin/dashboard");
        }
      }
    };

    document.addEventListener("click", handleGuideAction, true);
    return () => document.removeEventListener("click", handleGuideAction, true);
  }, [guide.finish]);

  return <AdminGettingStartedPage />;
}

export default AdminGettingStartedRoute;
