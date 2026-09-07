import { useParams } from "react-router-dom";
import { leaveGuideRoute } from "../features/guides/guideNavigation";
import useRoleGuide from "../features/guides/useRoleGuide";
import { useAdminSetupReadiness } from "../features/guides/useAdminSetupReadiness";
import { schoolYearProgress } from "../features/guides/schoolYearProgress";
import { useToast } from "../hooks/useToast";
import AdminGettingStartedPage from "../pages/admin/AdminGettingStartedPage";
import AdminGettingStartedStepPage from "../pages/admin/AdminGettingStartedStepPage";
import { getErrorMessage } from "../services/api";

export default function AdminGettingStartedRoute() {
  const setup = useAdminSetupReadiness();
  const guide = useRoleGuide({ role: "admin", completionMap: setup.loading || setup.error ? null : setup.data?.completion });
  const { showError } = useToast();
  const { step } = useParams();
  const onFinish = async () => {
    if (setup.loading || setup.error || !schoolYearProgress(setup.data?.completion).complete) return;
    try {
      await guide.finish();
      leaveGuideRoute("admin", "/admin/dashboard", { replace: true });
    } catch (error) {
      showError(getErrorMessage(error, "Could not save setup completion. Please try again."));
    }
  };
  return step ? <AdminGettingStartedStepPage setup={setup} /> : <AdminGettingStartedPage setup={setup} onFinish={onFinish} />;
}
