import { AlertTriangle, CalendarCheck2, RefreshCw, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import Button from "../../components/ui/Button";
import Input from "../../components/ui/Input";
import Badge from "../../components/ui/Badge";
import {
  CheckboxControl,
  WorkspacePanel,
} from "../academic-admin/AcademicWorkspacePrimitives";
import TypedConfirmationDialog from "../academic-admin/TypedConfirmationDialog";
import { schoolCalendarService } from "../schoolCalendar/api/schoolCalendarService";
import { academicService } from "../../services/academicService";
import { getErrorMessage } from "../../services/api";

const ACTIVATE_CONFIRMATION = "ACTIVATE_SCHOOL_CALENDAR";
const WEEKDAYS = [
  [0, "Mon"],
  [1, "Tue"],
  [2, "Wed"],
  [3, "Thu"],
  [4, "Fri"],
  [5, "Sat"],
  [6, "Sun"],
];

const DEFAULT_CONFIG = {
  timezone: "Africa/Lagos",
  instructional_weekdays: [0, 1, 2, 3, 4],
  default_open_time: "08:00",
  default_close_time: "15:00",
  default_student_attendance_required: true,
  default_workforce_attendance_required: true,
};

const asItems = (response) =>
  Array.isArray(response?.items) ? response.items : Array.isArray(response) ? response : [];

const titleCase = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function AdminCalendarSetupWorkspace({ setupTermId, onSaved }) {
  const [session, setSession] = useState(null);
  const [term, setTerm] = useState(null);
  const [calendar, setCalendar] = useState(null);
  const [configuration, setConfiguration] = useState(null);
  const [configForm, setConfigForm] = useState(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [confirmActivation, setConfirmActivation] = useState(false);
  const activationInFlightRef = useRef(false);

  const load = useCallback(async () => {
    if (!setupTermId) {
      setLoading(false);
      setError("Create the first academic term before preparing its calendar.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const [sessionResponse, termResponse, calendarResponse, configResponse] =
        await Promise.all([
          academicService.listSessions({ limit: 100 }),
          academicService.listTerms({ limit: 100 }),
          schoolCalendarService.listAdminCalendars({ limit: 100 }),
          schoolCalendarService.getConfiguration().catch((requestError) => {
            if (requestError?.response?.status === 404) return null;
            throw requestError;
          }),
        ]);
      const nextTerm = asItems(termResponse).find((item) => item.id === setupTermId) || null;
      const nextSession = asItems(sessionResponse).find(
        (item) => item.id === nextTerm?.academic_session_id,
      ) || null;
      const nextCalendar = asItems(calendarResponse).find(
        (item) => item.academic_term_id === setupTermId,
      ) || null;

      setTerm(nextTerm);
      setSession(nextSession);
      setCalendar(nextCalendar);
      setConfiguration(configResponse);
      if (configResponse) {
        setConfigForm({
          timezone: configResponse.timezone || DEFAULT_CONFIG.timezone,
          instructional_weekdays:
            configResponse.instructional_weekdays || DEFAULT_CONFIG.instructional_weekdays,
          default_open_time:
            configResponse.default_open_time || DEFAULT_CONFIG.default_open_time,
          default_close_time:
            configResponse.default_close_time || DEFAULT_CONFIG.default_close_time,
          default_student_attendance_required:
            configResponse.default_student_attendance_required,
          default_workforce_attendance_required:
            configResponse.default_workforce_attendance_required,
        });
      }
    } catch (requestError) {
      setError(getErrorMessage(requestError, "Could not load calendar setup."));
    } finally {
      setLoading(false);
    }
  }, [setupTermId]);

  useEffect(() => {
    load();
  }, [load]);

  const blockers = useMemo(() => calendar?.blocker_messages || [], [calendar]);
  const generated = Boolean(calendar?.generated_at);
  const active = calendar?.status === "active";
  const configurationCurrent =
    Boolean(configuration) && !calendar?.configuration_outdated;

  const run = async (key, action, fallbackMessage) => {
    setBusy(key);
    setError("");
    try {
      await action();
      await load();
      await onSaved?.();
      return true;
    } catch (requestError) {
      setError(getErrorMessage(requestError, fallbackMessage));
      return false;
    } finally {
      setBusy("");
    }
  };

  const saveConfiguration = async (event) => {
    event.preventDefault();
    await run(
      "configuration",
      () => schoolCalendarService.updateConfiguration(configForm),
      "Could not save calendar configuration.",
    );
  };

  const generate = async () => {
    if (!session?.id || !term?.id) return;
    await run(
      "generate",
      () =>
        schoolCalendarService.generateCalendar({
          academic_session_id: session.id,
          academic_term_id: term.id,
          overwrite_generated_days: generated,
        }),
      generated
        ? "Could not regenerate the term calendar."
        : "Could not generate the term calendar.",
    );
  };

  const activate = async () => {
    if (!calendar?.id || activationInFlightRef.current) return;
    const calendarId = calendar.id;
    activationInFlightRef.current = true;
    setConfirmActivation(false);
    try {
      await run(
        "activate",
        () => schoolCalendarService.activateCalendar(calendarId),
        "Could not activate the term calendar.",
      );
    } finally {
      activationInFlightRef.current = false;
    }
  };

  if (loading) {
    return <p role="status" className="py-8 text-sm text-text-muted">Checking calendar readiness...</p>;
  }

  return (
    <div className="space-y-4">
      {error ? (
        <div role="alert" className="rounded-xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.8fr)]">
        <WorkspacePanel
          title="1. Configure the school week"
          description="These defaults generate the first-term calendar. You can edit individual dates and exceptions after generation."
        >
          <form className="space-y-4" onSubmit={saveConfiguration}>
            <Input
              label="Timezone"
              value={configForm.timezone}
              onChange={(event) =>
                setConfigForm((current) => ({ ...current, timezone: event.target.value }))
              }
            />
            <div>
              <p className="mb-2 text-sm font-semibold text-text">Instructional weekdays</p>
              <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
                {WEEKDAYS.map(([value, label]) => {
                  const checked = configForm.instructional_weekdays.includes(value);
                  return (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={checked}
                      onClick={() =>
                        setConfigForm((current) => ({
                          ...current,
                          instructional_weekdays: checked
                            ? current.instructional_weekdays.filter((day) => day !== value)
                            : [...current.instructional_weekdays, value].sort((a, b) => a - b),
                        }))
                      }
                      className={`min-h-10 rounded-lg border px-2 text-xs font-semibold transition ${
                        checked
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border bg-surface text-text-muted"
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label="Opens at"
                type="time"
                value={configForm.default_open_time || ""}
                onChange={(event) =>
                  setConfigForm((current) => ({
                    ...current,
                    default_open_time: event.target.value,
                  }))
                }
              />
              <Input
                label="Closes at"
                type="time"
                value={configForm.default_close_time || ""}
                onChange={(event) =>
                  setConfigForm((current) => ({
                    ...current,
                    default_close_time: event.target.value,
                  }))
                }
              />
            </div>
            <CheckboxControl
              label="Students expected on open days"
              checked={configForm.default_student_attendance_required}
              onChange={(value) =>
                setConfigForm((current) => ({
                  ...current,
                  default_student_attendance_required: value,
                }))
              }
            />
            <CheckboxControl
              label="Workforce expected on open days"
              checked={configForm.default_workforce_attendance_required}
              onChange={(value) =>
                setConfigForm((current) => ({
                  ...current,
                  default_workforce_attendance_required: value,
                }))
              }
            />
            <Button
              type="submit"
              disabled={Boolean(busy) || configForm.instructional_weekdays.length === 0}
            >
              {busy === "configuration"
                ? "Saving..."
                : configuration
                  ? "Save configuration"
                  : "Create configuration"}
            </Button>
          </form>
        </WorkspacePanel>

        <WorkspacePanel
          title="2. Generate and activate"
          description="Activation finishes the basic school-year setup. It does not open the academic term."
        >
          <div className="space-y-4">
            <div className="grid gap-2 sm:grid-cols-2">
              <StatusMetric label="Session" value={`${session?.name || "Not found"} · ${titleCase(session?.status)}`} />
              <StatusMetric label="Term" value={`${titleCase(term?.name)} · ${titleCase(term?.status)}`} />
              <StatusMetric label="Calendar" value={titleCase(calendar?.status || "not generated")} />
              <StatusMetric label="Configuration" value={configuration ? `Revision ${configuration.revision}` : "Not configured"} />
            </div>

            <div className="rounded-xl border border-border bg-surface-muted/35 p-4">
              <div className="flex items-start gap-3">
                {active ? (
                  <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-success" />
                ) : blockers.length ? (
                  <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
                ) : (
                  <CalendarCheck2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                )}
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-text">
                    {active
                      ? "Calendar active"
                      : !generated
                        ? "Generate the calendar"
                        : calendar?.configuration_outdated
                          ? "Regenerate from the latest settings"
                          : calendar?.can_activate
                            ? "Ready for activation"
                            : "Resolve calendar blockers"}
                  </p>
                  <p className="mt-1 text-sm leading-6 text-text-muted">
                    {active
                      ? "The school-year foundation is complete. Term opening remains a separate operational action in the Academic Hub."
                      : "Review the generated evidence below. Backend lifecycle checks remain authoritative for activation."}
                  </p>
                </div>
              </div>
            </div>

            {blockers.length ? (
              <div className="space-y-2">
                {blockers.map((message) => (
                  <div key={message} className="rounded-lg border border-warning/30 bg-warning-soft px-3 py-2 text-sm text-text">
                    {message}
                  </div>
                ))}
              </div>
            ) : null}

            {generated ? (
              <div className="grid gap-2 sm:grid-cols-2">
                <StatusMetric label="Missing dates" value={Number(calendar?.missing_dates || 0)} />
                <StatusMetric label="Invalid dates" value={Number(calendar?.invalid_days || 0)} />
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={Boolean(busy) || !configuration || !session?.id || !term?.id || active}
                onClick={generate}
              >
                <RefreshCw className={`h-4 w-4 ${busy === "generate" ? "animate-spin" : ""}`} />
                {busy === "generate"
                  ? "Generating..."
                  : generated
                    ? "Regenerate calendar"
                    : "Generate calendar"}
              </Button>
              {generated && !active ? (
                <Link
                  to="/admin/academic/school-calendar?view=calendar"
                  className="inline-flex min-h-10 items-center rounded-lg border border-border px-3 text-sm font-semibold text-text transition hover:bg-surface-muted"
                >
                  Review dates & exceptions
                </Link>
              ) : null}
            </div>

            {!active ? (
              <Button
                type="button"
                disabled={
                  Boolean(busy) ||
                  confirmActivation ||
                  !calendar?.can_activate ||
                  !configurationCurrent
                }
                onClick={() => setConfirmActivation(true)}
              >
                {busy === "activate" ? "Activating..." : "Review and activate calendar"}
              </Button>
            ) : (
              <Badge variant="success">Basic school-year setup complete</Badge>
            )}
          </div>
        </WorkspacePanel>
      </div>

      <p className="text-sm leading-6 text-text-muted">
        Opening the term is intentionally not part of this setup. Continue in the Academic Hub to finish levels, classes, curriculum, teacher coverage, grading, and other readiness requirements before term opening.
      </p>

      <TypedConfirmationDialog
        open={confirmActivation}
        title="Activate term calendar"
        description="This publishes the generated operational calendar for the draft term. It does not open the term."
        confirmationText={ACTIVATE_CONFIRMATION}
        confirmLabel="Activate calendar"
        variant="primary"
        isLoading={busy === "activate"}
        confirmDisabled={!calendar?.can_activate}
        onConfirm={activate}
        onCancel={() => setConfirmActivation(false)}
      />
    </div>
  );
}

function StatusMetric({ label, value }) {
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2.5">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-1 text-sm font-semibold text-text">{value || "Not set"}</p>
    </div>
  );
}
