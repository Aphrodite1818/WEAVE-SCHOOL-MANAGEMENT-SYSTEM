import { ArrowLeft, ArrowRight, CheckCircle2, ExternalLink, Sparkles } from "lucide-react";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import GuideProgressStepper from "../../components/guides/GuideProgressStepper";
import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import useRoleGuide from "../../features/guides/useRoleGuide";

function RoleGettingStartedPage({ role }) {
  const navigate = useNavigate();
  const guide = useRoleGuide({ role });

  useEffect(() => {
    if (!guide.loading && guide.guideState?.status === "not_started") {
      guide.start();
    }
  }, [guide.guideState?.status, guide.loading, guide.start]);

  if (guide.loading || !guide.config || !guide.currentStep) {
    return (
      <DashboardLayout role={role} title="Getting started">
        <LoadingState label="Preparing your guide..." />
      </DashboardLayout>
    );
  }

  const current = guide.currentStep;
  const Icon = current.icon;
  const firstStep = guide.currentIndex === 0;
  const lastStep = guide.currentIndex >= guide.steps.length - 1;

  const openWorkspace = async () => {
    await guide.moveTo(current.id);
    navigate(current.to);
  };

  const markComplete = async () => {
    if (lastStep) {
      await guide.finish();
      navigate(guide.config.dashboardRoute, { replace: true });
      return;
    }
    await guide.advanceFrom(current.id);
  };

  const skipCurrent = async () => {
    await guide.skipStep(current.id);
    if (lastStep) navigate(guide.config.dashboardRoute, { replace: true });
  };

  const previous = async () => {
    if (firstStep) return;
    await guide.moveTo(guide.steps[guide.currentIndex - 1].id);
  };

  const hideGuide = async () => {
    await guide.dismiss();
    navigate(guide.config.dashboardRoute, { replace: true });
  };

  return (
    <DashboardLayout
      role={role}
      title="Getting started"
      description="A focused introduction that stays out of the way while you explore the real workspace."
    >
      <div className="space-y-5">
        <Card className="overflow-hidden border-primary/20 p-0">
          <div className="border-b border-border bg-primary-soft/45 px-4 py-5 sm:px-6 sm:py-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <div className="flex items-center gap-2 text-primary">
                  <Sparkles className="h-4 w-4" />
                  <p className="text-[11px] font-bold uppercase tracking-[0.16em]">
                    {guide.config.eyebrow}
                  </p>
                </div>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-text sm:text-3xl">
                  {guide.config.title}
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted sm:text-base">
                  {guide.config.description}
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="small"
                onClick={() => navigate(guide.config.dashboardRoute)}
                className="self-start lg:self-auto"
              >
                Finish later
              </Button>
            </div>
          </div>
          <div className="px-4 py-5 sm:px-6">
            <GuideProgressStepper
              steps={guide.steps}
              currentStepId={current.id}
              onStepSelect={(step) => guide.moveTo(step.id)}
            />
          </div>
        </Card>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
          <Card className="p-4 sm:p-6">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-primary-soft text-primary">
                {Icon ? <Icon className="h-5 w-5" /> : <CheckCircle2 className="h-5 w-5" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-text-faint">
                  Step {guide.currentIndex + 1} of {guide.steps.length}
                </p>
                <h3 className="mt-2 text-xl font-semibold text-text sm:text-2xl">
                  {current.label}
                </h3>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-text-muted">
                  {current.description}
                </p>

                <div className="mt-6 rounded-2xl border border-border bg-surface-muted/30 p-4">
                  <p className="text-sm font-semibold text-text">
                    Explore the real workspace
                  </p>
                  <p className="mt-1 text-sm leading-6 text-text-muted">
                    This guide does not cover the application with an overlay. Open the feature, use it normally, then return and mark the step complete.
                  </p>
                  <Button
                    type="button"
                    onClick={openWorkspace}
                    className="mt-4 w-full sm:w-auto"
                  >
                    {current.actionLabel}
                    <ExternalLink className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>

            <div className="mt-6 flex flex-col-reverse gap-2 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
              <Button
                type="button"
                variant="ghost"
                onClick={previous}
                disabled={firstStep}
              >
                <ArrowLeft className="h-4 w-4" />
                Previous
              </Button>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button type="button" variant="outline" onClick={skipCurrent}>
                  Skip this step
                </Button>
                <Button type="button" onClick={markComplete}>
                  {lastStep ? "Finish guide" : "Done, continue"}
                  {lastStep ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <ArrowRight className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </Card>

          <Card className="h-fit p-4 sm:p-5">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-text-faint">
              Guide progress
            </p>
            <div className="mt-3 flex items-end justify-between gap-3">
              <div>
                <p className="text-3xl font-semibold text-text">
                  {guide.completionPercent}%
                </p>
                <p className="mt-1 text-sm text-text-muted">
                  {guide.resolvedCount} of {guide.steps.length} steps resolved
                </p>
              </div>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-muted">
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-300"
                style={{ width: `${guide.completionPercent}%` }}
              />
            </div>
            <button
              type="button"
              onClick={hideGuide}
              className="mt-5 text-left text-sm font-semibold text-text-muted transition hover:text-text"
            >
              Do not show this introduction again
            </button>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default RoleGettingStartedPage;
