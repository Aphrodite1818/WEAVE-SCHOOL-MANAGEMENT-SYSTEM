import { useCallback, useEffect, useRef, useState } from "react";
import Button from "../../components/ui/Button";
import { academicService } from "../../services/academicService";
import { getErrorMessage, parseApiError } from "../../services/api";
import { subscriptionService } from "../../services/subscriptionService";
import { formatPlanName } from "../subscriptions/subscriptionConfig";
import { useSubscription } from "../subscriptions/useSubscription";
import DepartmentsWorkspace from "../academic-admin/DepartmentsWorkspace";
import TypedConfirmationDialog from "../academic-admin/TypedConfirmationDialog";

const money = (amount) => new Intl.NumberFormat("en-NG", {
  style: "currency", currency: "NGN", maximumFractionDigits: 0,
}).format(Number(amount || 0) / 100);

export default function AdminStartTermWorkspace({ termId, onSaved }) {
  const [options, setOptions] = useState(null);
  const [dependencies, setDependencies] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState(null);
  const [showSpecialization, setShowSpecialization] = useState(false);
  const lock = useRef(false);
  const { refreshSubscriptionState } = useSubscription();

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [preview, plans] = await Promise.all([
        academicService.getTermDependencies(termId),
        subscriptionService.getTermPlanOptions(termId),
      ]);
      setDependencies(preview);
      setOptions(plans);
    } catch (err) {
      setError(getErrorMessage(err, "Could not check this term's plan and opening requirements."));
    } finally { setLoading(false); }
  }, [termId]);
  useEffect(() => { load(); }, [load]);

  const openWithPlan = async () => {
    if (lock.current || !confirmation || !dependencies?.can_open) return;
    const option = confirmation;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      if (option.transition !== "current") {
        if (option.requires_payment || Number(option.amount_due_kobo) > 0) {
          const checkout = await subscriptionService.initializeTermCheckout({
            academic_term_id: termId, plan_code: option.plan_code,
          });
          subscriptionService.saveTermPaymentIntent({
            academicTermId: termId, reference: checkout.reference,
            origin: "guided-onboarding", returnPath: "/admin/getting-started/start_term",
            postPaymentAction: "open_term",
          });
          window.location.assign(subscriptionService.checkoutRedirectUrl(checkout));
          return;
        }
        if (option.plan_code === "free") await subscriptionService.activateFreeTerm(termId);
        else await subscriptionService.changeTermPlan({ academicTermId: termId, targetPlan: option.plan_code });
      }
      await academicService.openTerm(termId);
      await refreshSubscriptionState({ silent: true });
      await onSaved();
    } catch (err) {
      // A plan can be saved even when term opening fails. Reload it so a retry
      // opens the term with that plan instead of starting a second payment.
      await load();
      const parsed = parseApiError(err, "Could not open this term.");
      const details = parsed.data?.detail || parsed.data;
      setError([parsed.message, ...(details?.blocker_messages || [])].join(" "));
    } finally {
      lock.current = false;
      setBusy(false);
      setConfirmation(null);
    }
  };

  if (loading) return <p role="status" className="py-8 text-text-muted">Checking your term and available plans...</p>;
  const current = options?.options?.find((option) => option.transition === "current" && option.eligible);
  const ready = dependencies?.can_open === true;
  return <div className="space-y-6">
    {error ? <div role="alert" className="rounded-xl border border-border bg-surface p-5"><p className="text-sm leading-6 text-error">{error}</p><Button variant="outline" className="mt-4" disabled={busy} onClick={load}>Check again</Button></div> : null}
    {!ready && dependencies ? <section className="rounded-2xl border border-border bg-surface p-6">
      <h2 className="text-lg font-semibold">One more thing before starting</h2>
      <ul className="mt-3 space-y-2 text-sm leading-6 text-text-muted">{dependencies.blocker_messages?.map((message) => <li key={message}>{message}</li>)}</ul>
      {dependencies.dependency_counts?.classes_missing_department > 0 ? <Button variant="outline" className="mt-5" onClick={() => setShowSpecialization(!showSpecialization)}>{showSpecialization ? "Hide class specialization" : "Resolve class specialization"}</Button> : null}
      {showSpecialization ? <div className="mt-6"><DepartmentsWorkspace activeTab="placements" setupTermId={termId} /></div> : null}
      <Button className="ml-2 mt-5" onClick={load}>Check readiness again</Button>
    </section> : null}
    {options ? <>
      <p className="text-sm leading-7 text-text-muted">Your calendar is active. Choose the resources your school needs for this term. Payment is required only for a paid plan; Free is available when your school fits its limits.</p>
      {current ? <section className="rounded-2xl border border-border bg-surface p-7">
        <p className="text-sm text-text-muted">Plan selected for this term</p>
        <h2 className="mt-2 text-2xl font-semibold">{formatPlanName(current.plan_code)}</h2>
        <p className="mt-3 text-sm leading-6 text-text-muted">Your plan is saved. The next action opens the term; it does not take another payment.</p>
        <Button className="mt-6" disabled={busy || !ready} onClick={() => setConfirmation(current)}>Open term</Button>
      </section> : <div className="grid gap-4 sm:grid-cols-2">
        {options.options.map((option) => <section key={option.plan_code} className="flex flex-col rounded-2xl border border-border bg-surface p-6">
          <h2 className="text-lg font-semibold">{formatPlanName(option.plan_code)}</h2>
          <p className="mt-3 text-2xl font-semibold">{money(option.amount_due_kobo)}<span className="ml-2 text-xs font-normal text-text-muted">due for this term</span></p>
          <ul className="my-4 space-y-2 text-sm leading-6 text-text-muted">{(option.blockers || []).map((blocker) => <li key={blocker.resource}>{String(blocker.resource).replaceAll("_", " ")}: {blocker.used} used, {blocker.limit} allowed.</li>)}</ul>
          <Button className="mt-auto" disabled={busy || !ready || !option.eligible} onClick={() => setConfirmation(option)}>{option.requires_payment ? "Choose paid plan" : option.plan_code === "free" ? "Continue with Free" : "Use this plan"}</Button>
        </section>)}
      </div>}
    </> : null}
    <TypedConfirmationDialog open={Boolean(confirmation)} title={confirmation?.requires_payment ? "Continue to payment" : "Open this term"}
      description={confirmation?.requires_payment ? `Pay ${money(confirmation.amount_due_kobo)} for ${formatPlanName(confirmation.plan_code)}. After payment is verified, Weave will attempt to open this term and return you to setup.` : "This term will become the current term for your school."}
      confirmationText="OPEN_ACADEMIC_TERM" confirmLabel={confirmation?.requires_payment ? "Continue to secure payment" : "Open term"}
      variant="primary" isLoading={busy} onConfirm={openWithPlan} onCancel={() => setConfirmation(null)} />
  </div>;
}
