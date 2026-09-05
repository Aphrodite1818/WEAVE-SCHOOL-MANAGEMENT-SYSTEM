import { useToast } from "../../hooks/useToast";
import { getErrorMessage } from "../../services/api";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";


function AdminGettingStartedPage({ setup, guideState }) {
  const navigate = useNavigate();
  const { showError } = useToast();
  const steps = guideState.steps;
  const required = steps.filter((step) => !step.optional);
  const optional = steps.filter((step) => step.optional);
  const completed = required.filter((step) => setup.data?.completion?.[step.id] === true);
  const pending = required.filter((step) => setup.data?.completion?.[step.id] !== true);
  const current = pending.find((step) => step.id === guideState.guideState?.current_step) || pending[0];
  const openStep = async (step) => {
    await guideState.moveTo(step.id);
    navigate(`/admin/getting-started/${step.id}`);
  };
  return <DashboardLayout role="admin" title="School setup" description="Get this school operational. Progress reflects saved configuration and academic readiness."
    actions={<Button variant="outline" onClick={() => navigate("/admin/dashboard")}>Finish later</Button>}>
    <section className="mx-auto max-w-5xl space-y-4">
      <Card className="space-y-3 p-5">
        <h2 className="text-xl font-semibold">{completed.length} of {required.length} required steps complete</h2>
        <p className="text-sm text-text-muted">{setup.data?.session_name || "No session configured"} / {setup.data?.term_name?.replaceAll("_", " ") || "No term configured"}</p>
        <p className="text-sm text-text-muted">{setup.data?.note}</p>
        <Button variant="outline" disabled={setup.loading} onClick={setup.refresh}>{setup.loading ? "Checking setup..." : "Refresh readiness"}</Button>
        {setup.error ? <p role="alert" className="text-sm text-error">{setup.error}</p> : null}
        {!setup.loading && !setup.error && current ? <div className="border-t border-border pt-4">
          <p className="text-xs font-semibold uppercase text-text-muted">Current task</p>
          <h3 className="mt-2 text-lg font-semibold">{current.label}</h3>
          <p className="my-2 text-sm text-text-muted">{current.description}</p>
          <Button onClick={() => openStep(current).catch((error) => showError(getErrorMessage(error, "Could not save guide progress. Try again.")))}>{current.actionLabel}<ArrowRight className="h-4 w-4" /></Button>
        </div> : null}
        {!pending.length && !setup.loading && !setup.error ? <Button>Complete setup</Button> : null}
      </Card>
      {setup.data?.blockers?.length ? <Card className="p-5"><h3 className="font-semibold">Readiness blockers</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{setup.data.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul></Card> : null}
      <Card className="p-5"><h3 className="font-semibold">Upcoming tasks</h3><div className="mt-3 divide-y divide-border">{pending.filter((step) => step.id !== current?.id).map((step) => <div key={step.id} className="flex items-center justify-between gap-3 py-3"><div><p className="text-sm font-semibold">{step.label}</p><p className="text-sm text-text-muted">{step.description}</p></div><Button size="small" variant="outline" onClick={() => openStep(step).catch((error) => showError(getErrorMessage(error, "Could not save guide progress. Try again.")))}>Open</Button></div>)}</div></Card>
      <details className="rounded-xl border border-border bg-surface p-5"><summary className="cursor-pointer font-semibold">Completed ({completed.length})</summary><ul className="mt-3 space-y-2">{completed.map((step) => <li key={step.id} className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-success" />{step.label}</li>)}</ul></details>
      {optional.length ? <Card className="p-5"><h3 className="font-semibold">Optional setup</h3><p className="mt-1 text-sm text-text-muted">These capabilities do not block school setup.</p><div className="mt-3 flex flex-wrap gap-2">{optional.map((step) => <Button key={step.id} variant="outline" onClick={() => navigate(step.to)}>{step.actionLabel}</Button>)}</div></Card> : null}
    </section>
  </DashboardLayout>;
}

export default AdminGettingStartedPage;
