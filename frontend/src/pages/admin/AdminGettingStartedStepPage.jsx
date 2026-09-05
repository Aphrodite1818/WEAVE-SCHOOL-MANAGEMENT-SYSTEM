import { useSubscription } from "../../features/subscriptions/useSubscription";
import { ArrowLeft, ArrowRight, SkipForward } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { supportsDepartmentWorkflow } from "../../features/academic-admin/academicDepartmentCapability";
import AdminGuideTaskWorkspace from "../../features/guides/AdminGuideTaskWorkspace";
import { ROLE_GUIDES } from "../../features/guides/roleGuideConfig";
import { academicLevelService } from "../../services/academicsService";

const asItems = (value) => (Array.isArray(value) ? value : value?.items || []);

function AdminGettingStartedStepPage() {
  const navigate = useNavigate();
  const { entitlements } = useSubscription();
  const { step: stepId } = useParams();
  const [categoryOptions, setCategoryOptions] = useState([]);
  const [capabilitiesReady, setCapabilitiesReady] = useState(false);

  useEffect(() => {
    let mounted = true;
    academicLevelService
      .getCategories()
      .then((result) => {
        if (mounted) setCategoryOptions(asItems(result));
      })
      .catch(() => {
        if (mounted) setCategoryOptions([]);
      })
      .finally(() => {
        if (mounted) setCapabilitiesReady(true);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const steps = useMemo(() => {
    const configured = ROLE_GUIDES.admin.steps.filter((item) => !item.feature || entitlements?.features?.[item.feature] === true);
    if (!capabilitiesReady) return configured;
    return supportsDepartmentWorkflow(categoryOptions)
      ? configured
      : configured.filter((item) => item.id !== "departments");
  }, [capabilitiesReady, categoryOptions, entitlements]);

  if (!capabilitiesReady) return null;

  const index = steps.findIndex((item) => item.id === stepId);
  const step = steps[index];

  if (!step) {
    return <Navigate to="/admin/getting-started" replace />;
  }

  const Icon = step.icon;
  const previous = steps[index - 1];
  const next = steps[index + 1];
  const nextDestination = next
    ? `/admin/getting-started/${next.id}`
    : "/admin/getting-started";

  const navigation = (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <Button
        variant="outline"
        size="small"
        onClick={() =>
          navigate(
            previous
              ? `/admin/getting-started/${previous.id}`
              : "/admin/getting-started",
          )
        }
      >
        <ArrowLeft className="mr-2 h-4 w-4" />
        {previous ? `Previous: ${previous.shortLabel}` : "All setup steps"}
      </Button>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <Button
          variant="ghost"
          size="small"
          onClick={() => navigate(nextDestination)}
        >
          <SkipForward className="mr-2 h-4 w-4" />
          {next ? "Skip for now" : "Review setup"}
        </Button>
        {next ? (
          <Button size="small" onClick={() => navigate(nextDestination)}>
            Next: {next.shortLabel}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        ) : (
          <Button
            size="small"
            onClick={() => navigate("/admin/getting-started")}
          >
            Review setup
          </Button>
        )}
      </div>
    </div>
  );

  return (
    <DashboardLayout
      role="admin"
      title={step.label}
      description={step.description}
    >
      <section className="mx-auto max-w-7xl space-y-4">
        <Button
          variant="ghost"
          size="small"
          onClick={() => navigate("/admin/getting-started")}
        >
          <ArrowLeft className="mr-2 h-4 w-4" /> All setup steps
        </Button>

        <Card className="p-5 sm:p-7">
          <div className="flex items-start gap-4">
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-primary-soft text-primary">
              <Icon className="h-6 w-6" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold uppercase tracking-[0.12em] text-text-faint">
                Step {index + 1} of {steps.length}
              </p>
              <h2 className="mt-2 text-xl font-semibold text-text sm:text-2xl">
                {step.label}
              </h2>
              <p className="mt-2 text-sm leading-6 text-text-muted">
                {step.detail || step.description}
              </p>
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-border/70 bg-surface-muted/30 p-4">
            <h3 className="font-semibold text-text">What this page controls</h3>
            <p className="mt-1 text-sm leading-6 text-text-muted">
              {step.scope}
            </p>
          </div>

          <div className="mt-6">{navigation}</div>
        </Card>

        <div data-admin-guide-workspace={step.id}>
          <AdminGuideTaskWorkspace stepId={step.id} />
        </div>

        <Card className="p-4 sm:p-5">{navigation}</Card>
      </section>
    </DashboardLayout>
  );
}

export default AdminGettingStartedStepPage;
