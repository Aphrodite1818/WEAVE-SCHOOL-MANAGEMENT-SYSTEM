import { ArrowLeft, ArrowRight, CheckCircle2 } from "lucide-react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import SchoolYearProgress from "../../components/guides/SchoolYearProgress";
import AdminGuideTaskWorkspace from "../../features/guides/AdminGuideTaskWorkspace";
import { adminSchoolYearCompletion } from "../../features/guides/adminSchoolYearCompletion";
import { ROLE_GUIDES } from "../../features/guides/roleGuideConfig";
import { schoolYearProgress } from "../../features/guides/schoolYearProgress";
import { academicService } from "../../services/academicService";

export default function AdminGettingStartedStepPage({ setup }) {
  const navigate = useNavigate();
  const { step: stepId } = useParams();
  const steps = ROLE_GUIDES.admin.steps;
  const index = steps.findIndex((item) => item.id === stepId);
  const step = steps[index];
  const completion = adminSchoolYearCompletion(setup.data);
  const progress = schoolYearProgress(completion);
  const checking = setup.loading || Boolean(setup.error);
  const next = steps[index + 1];

  if (!step) return <Navigate to="/admin/getting-started" replace />;

  const goNext = () =>
    navigate(next ? `/admin/getting-started/${next.id}` : "/admin/getting-started");

  const onSaved = async () => {
    let data = (await setup.refresh()) || setup.data;

    if (
      step.id === "term" &&
      data?.completion?.term === true &&
      data?.academic_session_id &&
      data?.session_status === "draft"
    ) {
      await academicService.openSession(data.academic_session_id);
      data = (await setup.refresh()) || data;
    }

    const refreshedCompletion = adminSchoolYearCompletion(data);
    if (step.id !== "calendar" && refreshedCompletion?.[step.id] === true) {
      goNext();
    }
  };

  const complete = completion?.[step.id] === true;

  return (
    <DashboardLayout role="admin">
      <section
        className={`school-year-setup mx-auto py-4 sm:py-8 ${
          step.id === "calendar" ? "max-w-5xl" : "max-w-2xl"
        }`}
      >
        <button
          type="button"
          className="mb-8 flex min-h-11 items-center gap-2 text-sm font-medium text-text-muted"
          onClick={() => navigate("/admin/getting-started")}
        >
          <ArrowLeft className="h-4 w-4" />
          School year setup
        </button>

        <SchoolYearProgress
          completion={completion}
          current={step.id}
          disabled={checking}
          onSelect={(item) => navigate(`/admin/getting-started/${item.id}`)}
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
                  : "Your term calendar is active. The term remains closed until the rest of the academic setup is ready."}
            </p>
            <Button className="mt-6" onClick={goNext}>
              {next ? `Continue to ${next.shortLabel.toLowerCase()}` : "Finish setup"}
              <ArrowRight className="h-4 w-4" />
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
    </DashboardLayout>
  );
}
