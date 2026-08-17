import { ArrowLeft, ArrowRight } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { ROLE_GUIDES } from "../../features/guides/roleGuideConfig";

function AdminGettingStartedStepPage() {
  const navigate = useNavigate();
  const { step: stepId } = useParams();
  const steps = ROLE_GUIDES.admin.steps;
  const index = steps.findIndex((item) => item.id === stepId);
  const step = steps[index];

  if (!step) {
    navigate("/admin/getting-started", { replace: true });
    return null;
  }

  const Icon = step.icon;
  const next = steps[index + 1];

  return (
    <DashboardLayout role="admin" title={step.label} description={step.description}>
      <section className="mx-auto max-w-3xl space-y-4">
        <Button variant="ghost" size="small" onClick={() => navigate("/admin/getting-started")}>
          <ArrowLeft className="mr-2 h-4 w-4" /> All setup steps
        </Button>

        <Card className="p-5 sm:p-7">
          <div className="flex items-start gap-4">
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-primary-soft text-primary">
              <Icon className="h-6 w-6" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold uppercase tracking-[0.12em] text-text-faint">Step {index + 1} of {steps.length}</p>
              <h2 className="mt-2 text-xl font-semibold text-text sm:text-2xl">{step.label}</h2>
              <p className="mt-2 text-sm leading-6 text-text-muted">{step.detail || step.description}</p>
            </div>
          </div>

          <div className="mt-6 rounded-2xl border border-border/70 bg-surface-muted/30 p-4">
            <h3 className="font-semibold text-text">What this page controls</h3>
            <p className="mt-1 text-sm leading-6 text-text-muted">{step.scope}</p>
          </div>

          <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <Button variant="outline" onClick={() => navigate(step.to)}>{step.actionLabel}</Button>
            {next ? (
              <Button variant="ghost" onClick={() => navigate(`/admin/getting-started/${next.id}`)}>
                Next: {next.shortLabel}<ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
              <Button onClick={() => navigate("/admin/getting-started")}>Complete setup</Button>
            )}
          </div>
        </Card>
      </section>
    </DashboardLayout>
  );
}

export default AdminGettingStartedStepPage;
