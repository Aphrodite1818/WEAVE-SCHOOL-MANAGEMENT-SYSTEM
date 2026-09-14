import { ArrowLeft, ArrowRight, CheckCircle2, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import SchoolYearProgress from "../../components/guides/SchoolYearProgress";
import AdminGuideTaskWorkspace from "../../features/guides/AdminGuideTaskWorkspace";
import { adminSchoolYearCompletion } from "../../features/guides/adminSchoolYearCompletion";
import { ROLE_GUIDES } from "../../features/guides/roleGuideConfig";
import { schoolYearProgress } from "../../features/guides/schoolYearProgress";
import TypedConfirmationDialog from "../../features/academic-admin/TypedConfirmationDialog";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";

const OPEN_SESSION_CONFIRMATION = "OPEN_ACADEMIC_SESSION";

export default function AdminGettingStartedStepPage({ setup }) {
  const navigate = useNavigate();
  const { step: stepId } = useParams();
  const [confirmOpenSession, setConfirmOpenSession] = useState(false);
  const [openingSession, setOpeningSession] = useState(false);
  const [lifecycleError, setLifecycleError] = useState("");
  const steps = ROLE_GUIDES.admin.steps;
  const index = steps.findIndex((item) => item.id === stepId);
  const step = steps[index];
  const completion = adminSchoolYearCompletion(setup.data);
  const progress = schoolYearProgress(completion);
  const checking = setup.loading || Boolean(setup.error);
  const next = steps[index + 1];
  const previous = steps[index - 1];

  if (!step) return <Navigate to="/admin/getting-started" replace />;

  const goNext = () =>
    navigate(next ? `/admin/getting-started/${next.id}` : "/admin/getting-started");

  const onSaved = async () => {
    const data = (await setup.refresh()) || setup.data;
    const refreshedCompletion = adminSchoolYearCompletion(data);
    if (step.id !== "calendar" && refreshedCompletion?.[step.id] === true) {
      goNext();
    }
  };

  const openParentSession = async () => {
    if (!setup.data?.academic_session_id || openingSession) return;
    setOpeningSession(true);
    setLifecycleError("");
    try {
      await academicService.openSession(setup.data.academic_session_id);
      const data = (await setup.refresh()) || setup.data;
      if (adminSchoolYearCompletion(data).term === true) goNext();
    } catch (error) {
      setLifecycleError(
        getErrorMessage(
          error,
          "The academic session could not be opened. Review the lifecycle blockers and try again.",
        ),
      );
    } finally {
      setOpeningSession(false);
      setConfirmOpenSession(false);
    }
  };

  const complete = completion?.[step.id] === true;
  const canGoBack = Boolean(previous && setup.data?.session_status !== "open");
  const needsSessionOpen =
    step.id === "term" &&
    setup.data?.completion?.term === true &&
    setup.data?.session_status === "draft" &&
    !complete;

  return (
    <DashboardLayout role="admin">
      <section
        className={`school-year-setup mx-auto py-4 sm:py-8 ${
          step.id === "calendar" ? "max-w-5xl" : "max-w-2xl"
        }`}
      >
        <div className="mb-8 flex flex-wrap items-center gap-x-5 gap-y-2">
          <button
            type="button"
            className="flex min-h-11 items-center gap-2 text-sm font-medium text-text-muted"
            onClick={() => navigate("/admin/getting-started")}
          >
            <ArrowLeft className="h-4 w-4" />
            School year setup
          </button>
          {canGoBack ? (
            <button
              type="button"
              className="min-h-11 text-sm font-semibold text-primary underline-offset-4 hover:underline"
              onClick={() => navigate(`/admin/getting-started/${previous.id}`)}
            >
              Back to {previous.shortLabel.toLowerCase()}
            </button>
          ) : null}
        </div>

        <SchoolYearProgress
          completion={completion}
          current={step.id}
          disabled={checking}
          onSelect={(item) => {
            const targetIndex = steps.findIndex((candidate) => candidate.id === item.id);
            if (targetIndex < index && !canGoBack) return;
            navigate(`/admin/getting-started/${item.id}`);
          }}
        />

        <h1 className="text-3xl font-semibold tracking-tight text-text">{step.label}</h1>
        <p className="mb-8 mt-3 text-base leading-7 text-text-muted">
          {step.description}
        </p>

        {setup.error ? (
          <div role="alert">
            <p className="text-sm text-error">{setup.error}</p>
            <Button className="mt-4" variant="outline" onClick={setup.refresh}>
              Try again
            </Button>
          </div>
        ) : setup.loading && !setup.data ? (
          <p role="status" className="py-8 text-text-muted">
            Checking your saved setup...
          </p>
        ) : !progress.canOpen(step.id) ? (
          <div className="rounded-xl border border-border bg-surface p-6">
            <p className="text-sm text-text-muted">
              Complete the earlier milestone before continuing. The calendar becomes available only after the first term exists and its session has been opened successfully.
            </p>
            <Button
              className="mt-4"
              onClick={() => navigate(`/admin/getting-started/${progress.nextStep}`)}
            >
              Continue setup
            </Button>
          </div>
        ) : complete ? (
          <div className="rounded-2xl border border-border bg-surface p-8">
            <CheckCircle2 className="h-8 w-8 text-success" />
            <h2 className="mt-4 text-xl font-semibold">{step.shortLabel} is ready</h2>
            <p className="mt-3 text-sm text-text-muted">
              {step.id === "session"
                ? setup.data.session_name
                : step.id === "term"
                  ? `${setup.data.term_name?.replaceAll("_", " ")} is created and the session is open.`
                  : "Your term calendar is active. The term remains draft until the rest of the academic setup is ready."}
            </p>
            <Button className="mt-6" onClick={goNext}>
              {next ? `Continue to ${next.shortLabel.toLowerCase()}` : "Finish setup"}
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        ) : needsSessionOpen ? (
          <div className="rounded-2xl border border-border bg-surface p-7">
            <div className="flex items-start gap-3">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                <ShieldCheck className="h-5 w-5" />
              </span>
              <div>
                <h2 className="text-lg font-semibold text-text">Open the academic session</h2>
                <p className="mt-2 text-sm leading-6 text-text-muted">
                  {setup.data?.term_name?.replaceAll("_", " ") || "Your first term"} is saved. Opening {setup.data?.session_name || "the session"} makes it the current school year and unlocks calendar setup. The term itself stays draft.
                </p>
              </div>
            </div>
            {lifecycleError ? (
              <p role="alert" className="mt-4 rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
                {lifecycleError}
              </p>
            ) : null}
            <Button
              className="mt-6"
              disabled={openingSession}
              onClick={() => setConfirmOpenSession(true)}
            >
              {openingSession ? "Opening session..." : "Review and open session"}
            </Button>
          </div>
        ) : (
          <AdminGuideTaskWorkspace
            stepId={step.id}
            onSaved={onSaved}
            setupSessionId={setup.data?.academic_session_id}
            setupTermId={setup.data?.academic_term_id}
            setupSessionName={setup.data?.session_name}
          />
        )}
      </section>

      <TypedConfirmationDialog
        open={confirmOpenSession}
        title="Open academic session"
        description="This makes the session current. The first term remains draft so you can prepare its calendar and finish the rest of the academic setup before term opening."
        confirmationText={OPEN_SESSION_CONFIRMATION}
        confirmLabel="Open session"
        variant="primary"
        isLoading={openingSession}
        onConfirm={openParentSession}
        onCancel={() => setConfirmOpenSession(false)}
      />
    </DashboardLayout>
  );
}
