import { ArrowRight, CheckCircle2, GraduationCap } from "lucide-react";
import { useNavigate } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { ROLE_GUIDES } from "../../features/guides/roleGuideConfig";

function AdminGettingStartedPage() {
  const navigate = useNavigate();
  const guide = ROLE_GUIDES.admin;

  return (
    <DashboardLayout
      role="admin"
      title="School setup"
      description="Configure one school function at a time. You can leave and continue later without losing completed work."
      actions={<Button variant="outline" size="small" onClick={() => navigate("/admin/dashboard")}>Finish later</Button>}
    >
      <section className="mx-auto max-w-5xl space-y-5">
        <Card className="p-5 sm:p-6">
          <div className="flex items-start gap-4">
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-primary-soft text-primary">
              <GraduationCap className="h-6 w-6" />
            </span>
            <div>
              <h2 className="text-xl font-semibold text-text sm:text-2xl">Set up the academic workspace</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
                Each page below owns one responsibility. Complete the school structure first, then curriculum and operational periods. Nothing is hidden inside a long setup form.
              </p>
            </div>
          </div>
        </Card>

        <div className="grid gap-3 md:grid-cols-2">
          {guide.steps.map((step, index) => {
            const Icon = step.icon || CheckCircle2;
            return (
              <button
                key={step.id}
                type="button"
                onClick={() => navigate(`/admin/getting-started/${step.id}`)}
                className="rounded-2xl border border-border/70 bg-surface p-4 text-left transition hover:border-primary/40 hover:bg-primary-soft/20"
              >
                <div className="flex items-start gap-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-surface-muted text-text-soft"><Icon className="h-5 w-5" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-text-faint">Step {index + 1}</p>
                    <h3 className="mt-1 font-semibold text-text">{step.label}</h3>
                    <p className="mt-1 text-sm leading-5 text-text-muted">{step.description}</p>
                  </div>
                  <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-text-faint" />
                </div>
              </button>
            );
          })}
        </div>
      </section>
    </DashboardLayout>
  );
}

export default AdminGettingStartedPage;
