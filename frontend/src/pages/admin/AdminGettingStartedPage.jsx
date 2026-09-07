import { ArrowRight, CheckCircle2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import SchoolYearProgress from "../../components/guides/SchoolYearProgress";
import { ROLE_GUIDES } from "../../features/guides/roleGuideConfig";
import { schoolYearProgress } from "../../features/guides/schoolYearProgress";

export default function AdminGettingStartedPage({ setup, onFinish }) {
  const navigate = useNavigate();
  const progress = schoolYearProgress(setup.data?.completion);
  const checking = setup.loading || Boolean(setup.error);
  const current = ROLE_GUIDES.admin.steps.find((step) => step.id === progress.nextStep);
  const openStep = (step) => navigate(`/admin/getting-started/${step.id}`);
  return <DashboardLayout role="admin">
    <section className="mx-auto max-w-3xl py-4 sm:py-10">
      <p className="text-sm font-medium text-primary">A good place to begin</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight text-text sm:text-4xl">{!checking && progress.complete ? "Your basic setup is complete." : "Set up your school year."}</h1>
      <p className="mb-10 mt-4 max-w-xl text-base leading-7 text-text-muted">Start with a session, a term, and a calendar. You can add departments, classes, and other school details in the Academic Hub later.</p>
      <SchoolYearProgress completion={setup.data?.completion} current={current?.id} disabled={checking} onSelect={openStep} />
      {setup.error ? <div role="alert" className="mb-6 rounded-xl border border-border p-5"><p className="text-sm text-error">{setup.error}</p><Button className="mt-3" variant="outline" onClick={setup.refresh}>Try again</Button></div> : null}
      <div className="divide-y divide-border rounded-2xl border border-border bg-surface px-6 sm:px-8">
        {ROLE_GUIDES.admin.steps.map((step, index) => {
          const complete = !checking && setup.data?.completion?.[step.id] === true;
          const Icon = complete ? CheckCircle2 : step.icon;
          return <div key={step.id} className="flex items-start gap-4 py-7">
            <Icon className={`mt-1 h-6 w-6 shrink-0 ${complete ? "text-success" : "text-text-muted"}`} />
            <div className="min-w-0 flex-1"><h2 className="text-base font-semibold text-text">{index + 1}. {step.shortLabel}</h2><p className="mt-2 text-sm leading-6 text-text-muted">{step.description}</p>
              {complete ? <p className="mt-2 text-sm font-medium text-success">{step.id === "session" ? setup.data.session_name : step.id === "term" ? setup.data.term_name?.replaceAll("_", " ") : "Calendar active"}</p> : null}
            </div>
            {complete ? <span className="text-xs font-medium text-success">Done</span> : null}
          </div>;
        })}
      </div>
      {!checking ? <div className="mt-8">
        {current ? <Button onClick={() => openStep(current)}>{progress.completedCount ? "Continue setup" : "Set up session"}<ArrowRight className="h-4 w-4" /></Button> : <>
          <p className="mb-5 text-sm leading-6 text-text-muted">Your academic foundation is ready. The Academic Hub will guide you through any further requirements when you open a term or prepare results.</p>
          <Button onClick={onFinish}>Go to dashboard<ArrowRight className="h-4 w-4" /></Button>
        </>}
      </div> : null}
    </section>
  </DashboardLayout>;
}
