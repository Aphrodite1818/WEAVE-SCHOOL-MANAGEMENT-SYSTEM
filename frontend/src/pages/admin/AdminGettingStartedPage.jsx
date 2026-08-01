import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CalendarCheck2,
  CalendarDays,
  Check,
  CheckCircle2,
  CircleDashed,
  Clock3,
  GraduationCap,
  Loader2,
  RefreshCw,
  School,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import GuideProgressStepper from "../../components/guides/GuideProgressStepper";
import DashboardLayout from "../../components/layout/DashboardLayout";
import LoadingState from "../../components/shared/LoadingState";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { schoolCalendarService } from "../../features/schoolCalendar/api/schoolCalendarService";
import useRoleGuide from "../../features/guides/useRoleGuide";
import { useToast } from "../../hooks/useToast";
import { academicService } from "../../services/academicService";
import { classService } from "../../services/academicsService";
import { getErrorMessage } from "../../services/api";
import { subjectService } from "../../services/subject.service";

const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const isoDate = (date = new Date()) => date.toISOString().slice(0, 10);
const addMonths = (date, months) => {
  const next = new Date(date);
  next.setMonth(next.getMonth() + months);
  return isoDate(next);
};
const titleCase = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
const statusValue = (item) => String(item?.status || "").toLowerCase();
const sessionLabel = (item) => item?.name || "Academic session";
const termLabel = (item) => titleCase(item?.display_name || item?.name || "Term");
const classLabel = (item) =>
  [item?.name, item?.arm].filter(Boolean).join(" ") || "Class";

const today = new Date();
const DEFAULT_SESSION = {
  name: `${today.getFullYear()}/${today.getFullYear() + 1}`,
  start_date: isoDate(today),
  end_date: addMonths(today, 11),
};
const DEFAULT_TERM = {
  name: "first_term",
  start_date: isoDate(today),
  end_date: addMonths(today, 4),
};
const DEFAULT_CALENDAR = {
  timezone: "Africa/Lagos",
  default_open_time: "08:00",
  default_close_time: "15:00",
};

function SetupCheck({ label, complete, detail }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border/70 bg-surface px-3 py-3">
      <span
        className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full ${
          complete
            ? "bg-success text-white"
            : "border border-border bg-surface-muted text-text-faint"
        }`}
      >
        {complete ? <Check className="h-3.5 w-3.5" /> : <CircleDashed className="h-3.5 w-3.5" />}
      </span>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-text">{label}</p>
        {detail ? <p className="mt-0.5 text-xs leading-5 text-text-muted">{detail}</p> : null}
      </div>
    </div>
  );
}

function StepHeading({ step, number, total, complete }) {
  const Icon = step.icon;
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
      <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-primary-soft text-primary">
        {Icon ? <Icon className="h-5 w-5" /> : <Sparkles className="h-5 w-5" />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-text-faint">
            Step {number} of {total}
          </p>
          {complete ? <Badge variant="success">Complete</Badge> : null}
        </div>
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-text sm:text-2xl">
          {step.label}
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-7 text-text-muted">
          {step.description}
        </p>
      </div>
    </div>
  );
}

function AdminGettingStartedPage() {
  const navigate = useNavigate();
  const { showSuccess, showError } = useToast();
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [calendars, setCalendars] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [calendarConfiguration, setCalendarConfiguration] = useState(null);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [selectedTermId, setSelectedTermId] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [sessionForm, setSessionForm] = useState(DEFAULT_SESSION);
  const [termForm, setTermForm] = useState(DEFAULT_TERM);
  const [calendarForm, setCalendarForm] = useState(DEFAULT_CALENDAR);
  const [classForm, setClassForm] = useState({ name: "", arm: "" });
  const [subjectForm, setSubjectForm] = useState({ name: "", code: "" });

  const loadSetup = useCallback(async ({ quiet = false } = {}) => {
    if (quiet) setRefreshing(true);
    else setLoading(true);
    setError("");
    try {
      const [
        sessionResponse,
        termResponse,
        calendarResponse,
        classResponse,
        subjectResponse,
        configurationResponse,
      ] = await Promise.all([
        academicService.listSessions({ limit: 100 }),
        academicService.listTerms({ limit: 100 }),
        schoolCalendarService.listAdminCalendars({ limit: 100 }),
        classService.getClasses({ limit: 100, activeOnly: false }),
        subjectService.getSubjects({ limit: 100, includeArchived: false }),
        schoolCalendarService.getConfiguration().catch((requestError) => {
          if (requestError?.response?.status === 404) return null;
          throw requestError;
        }),
      ]);

      const sessionItems = asItems(sessionResponse);
      const termItems = asItems(termResponse);
      const calendarItems = asItems(calendarResponse);
      const classItems = asItems(classResponse);
      const subjectItems = asItems(subjectResponse);
      const preferredSession =
        sessionItems.find((item) => item.is_current) ||
        sessionItems.find((item) => statusValue(item) === "open") ||
        sessionItems.find((item) => statusValue(item) === "draft") ||
        sessionItems[0] ||
        null;
      const preferredTerms = termItems.filter(
        (item) => !preferredSession || item.academic_session_id === preferredSession.id,
      );
      const preferredTerm =
        preferredTerms.find((item) => item.is_current) ||
        preferredTerms.find((item) => statusValue(item) === "open") ||
        preferredTerms.find((item) => statusValue(item) === "draft") ||
        preferredTerms[0] ||
        null;

      setSessions(sessionItems);
      setTerms(termItems);
      setCalendars(calendarItems);
      setClasses(classItems);
      setSubjects(subjectItems);
      setCalendarConfiguration(configurationResponse);
      setSelectedSessionId((current) =>
        sessionItems.some((item) => item.id === current)
          ? current
          : preferredSession?.id || "",
      );
      setSelectedTermId((current) =>
        termItems.some((item) => item.id === current)
          ? current
          : preferredTerm?.id || "",
      );
      if (configurationResponse) {
        setCalendarForm({
          timezone: configurationResponse.timezone || DEFAULT_CALENDAR.timezone,
          default_open_time:
            configurationResponse.default_open_time || DEFAULT_CALENDAR.default_open_time,
          default_close_time:
            configurationResponse.default_close_time || DEFAULT_CALENDAR.default_close_time,
        });
      }
    } catch (requestError) {
      const message = getErrorMessage(requestError, "Could not load the school setup state.");
      setError(message);
      showError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [showError]);

  useEffect(() => {
    loadSetup();
  }, [loadSetup]);

  const selectedSession = useMemo(
    () => sessions.find((item) => item.id === selectedSessionId) || null,
    [selectedSessionId, sessions],
  );
  const termsForSession = useMemo(
    () =>
      terms.filter(
        (item) => !selectedSessionId || item.academic_session_id === selectedSessionId,
      ),
    [selectedSessionId, terms],
  );
  const selectedTerm = useMemo(
    () =>
      termsForSession.find((item) => item.id === selectedTermId) ||
      termsForSession.find((item) => item.is_current) ||
      termsForSession[0] ||
      null,
    [selectedTermId, termsForSession],
  );
  const calendarsForTerm = useMemo(
    () =>
      calendars.filter(
        (item) => !selectedTerm?.id || item.academic_term_id === selectedTerm.id,
      ),
    [calendars, selectedTerm],
  );
  const selectedCalendar = useMemo(
    () =>
      calendarsForTerm.find((item) => statusValue(item) === "active") ||
      calendarsForTerm[0] ||
      null,
    [calendarsForTerm],
  );

  useEffect(() => {
    if (!selectedSessionId) {
      setSelectedTermId("");
      return;
    }
    if (selectedTerm?.id) setSelectedTermId(selectedTerm.id);
  }, [selectedSessionId, selectedTerm?.id]);

  const sessionActive = Boolean(
    selectedSession &&
      statusValue(selectedSession) === "open" &&
      selectedSession.is_current,
  );
  const termActive = Boolean(
    selectedTerm && statusValue(selectedTerm) === "open" && selectedTerm.is_current,
  );
  const calendarActive = statusValue(selectedCalendar) === "active";
  const sessionDraft = statusValue(selectedSession) === "draft";
  const termDraft = statusValue(selectedTerm) === "draft";
  const sessionDatesComplete = Boolean(
    selectedSession?.start_date && selectedSession?.end_date,
  );
  const termDatesComplete = Boolean(selectedTerm?.start_date && selectedTerm?.end_date);
  const calendarPrepared = Boolean(
    calendarConfiguration &&
      selectedCalendar &&
      !selectedCalendar.configuration_outdated &&
      Number(selectedCalendar.missing_dates || 0) === 0 &&
      Number(selectedCalendar.extra_dates || 0) === 0 &&
      Number(selectedCalendar.duplicate_dates || 0) === 0 &&
      Number(selectedCalendar.invalid_days || 0) === 0 &&
      Number(selectedCalendar.dependency_counts?.unresolved_days || 0) === 0,
  );
  const calendarBlockers = Array.isArray(selectedCalendar?.blocker_messages)
    ? selectedCalendar.blocker_messages
    : [];
  const anotherOpenTerm = terms.find(
    (item) =>
      item.id !== selectedTerm?.id &&
      statusValue(item) === "open" &&
      item.is_current,
  );
  const sessionOpenReady = Boolean(
    selectedSession &&
      sessionDraft &&
      sessionDatesComplete &&
      selectedTerm &&
      calendarConfiguration,
  );
  const calendarActivationReady = Boolean(
    selectedCalendar &&
      calendarPrepared &&
      sessionActive &&
      termDraft &&
      selectedCalendar.can_activate !== false,
  );
  const termOpenReady = Boolean(
    selectedTerm &&
      termDraft &&
      termDatesComplete &&
      sessionActive &&
      calendarActive &&
      !anotherOpenTerm,
  );
  const completionMap = useMemo(
    () => ({
      session: Boolean(selectedSession),
      term: Boolean(selectedSession && selectedTerm),
      calendar: calendarPrepared,
      structure: classes.length > 0 && subjects.length > 0,
      session_open: sessionActive,
      calendar_active: calendarActive,
      term_open: termActive,
    }),
    [
      calendarActive,
      calendarPrepared,
      classes.length,
      selectedSession,
      selectedTerm,
      sessionActive,
      subjects.length,
      termActive,
    ],
  );
  const guide = useRoleGuide({ role: "admin", completionMap });

  useEffect(() => {
    if (!guide.loading && guide.guideState?.status === "not_started") {
      guide.start();
    }
  }, [guide.guideState?.status, guide.loading, guide.start]);

  const runAction = async (key, action, successMessage) => {
    setSaving(key);
    setError("");
    try {
      const result = await action();
      if (successMessage) showSuccess(successMessage);
      await loadSetup({ quiet: true });
      return result;
    } catch (requestError) {
      const message = getErrorMessage(requestError, "Setup action failed.");
      setError(message);
      showError(message);
      return null;
    } finally {
      setSaving("");
    }
  };

  const createSession = async (event) => {
    event.preventDefault();
    const created = await runAction(
      "session",
      () => academicService.createSession(sessionForm),
      "Academic session created.",
    );
    if (!created?.id) return;
    setSelectedSessionId(created.id);
    await guide.moveTo("term");
  };

  const createTerm = async (event) => {
    event.preventDefault();
    if (!selectedSessionId) {
      showError("Create or select an academic session first.");
      return;
    }
    const created = await runAction(
      "term",
      () =>
        academicService.createTerm({
          ...termForm,
          academic_session_id: selectedSessionId,
        }),
      "Academic term created.",
    );
    if (!created?.id) return;
    setSelectedTermId(created.id);
    await guide.moveTo("calendar");
  };

  const generateCalendar = async (event) => {
    event.preventDefault();
    if (!selectedSessionId || !selectedTerm?.id) {
      showError("Create and select a session and term before generating the calendar.");
      return;
    }
    const result = await runAction(
      "calendar",
      async () => {
        await schoolCalendarService.updateConfiguration({
          timezone: calendarForm.timezone,
          instructional_weekdays: [0, 1, 2, 3, 4],
          default_open_time: calendarForm.default_open_time,
          default_close_time: calendarForm.default_close_time,
          default_student_attendance_required: true,
          default_workforce_attendance_required: true,
        });
        return schoolCalendarService.generateCalendar({
          academic_session_id: selectedSessionId,
          academic_term_id: selectedTerm.id,
          overwrite_generated_days: Boolean(selectedCalendar),
        });
      },
      "School calendar generated.",
    );
    if (result) await guide.moveTo("structure");
  };

  const createClass = async (event) => {
    event.preventDefault();
    const created = await runAction(
      "class",
      () => classService.createClass(classForm),
      "Class created.",
    );
    if (!created) return;
    setClassForm({ name: "", arm: "" });
    if (subjects.length > 0) await guide.moveTo("session_open");
  };

  const createSubject = async (event) => {
    event.preventDefault();
    const created = await runAction(
      "subject",
      () => subjectService.createSubject({ ...subjectForm, description: "" }),
      "Subject created.",
    );
    if (!created) return;
    setSubjectForm({ name: "", code: "" });
    if (classes.length > 0) await guide.moveTo("session_open");
  };

  const openSession = async () => {
    if (!selectedSession?.id) return;
    const result = await runAction(
      "open-session",
      () => academicService.openSession(selectedSession.id),
      "Academic session opened.",
    );
    if (result) await guide.moveTo("calendar_active");
  };

  const activateCalendar = async () => {
    if (!selectedCalendar?.id) return;
    const result = await runAction(
      "activate-calendar",
      () => schoolCalendarService.activateCalendar(selectedCalendar.id),
      "School calendar activated.",
    );
    if (result) await guide.moveTo("term_open");
  };

  const openTerm = async () => {
    if (!selectedTerm?.id) return;
    const result = await runAction(
      "open-term",
      () => academicService.openTerm(selectedTerm.id),
      "Academic term opened.",
    );
    if (result) await guide.finish();
  };

  if (loading || guide.loading || !guide.config || !guide.currentStep) {
    return (
      <DashboardLayout role="admin" title="School setup">
        <LoadingState label="Preparing your school setup..." />
      </DashboardLayout>
    );
  }

  const current = guide.currentStep;
  const currentComplete = Boolean(completionMap[current.id]);
  const firstStep = guide.currentIndex === 0;
  const lastStep = guide.currentIndex >= guide.steps.length - 1;
  const sessionOptions = sessions.map((item) => ({
    value: item.id,
    label: sessionLabel(item),
    description: `${titleCase(item.status)}${item.is_current ? " · Current" : ""}`,
  }));
  const termOptions = termsForSession.map((item) => ({
    value: item.id,
    label: termLabel(item),
    description: `${titleCase(item.status)}${item.is_current ? " · Current" : ""}`,
  }));

  const goPrevious = () => {
    if (!firstStep) guide.moveTo(guide.steps[guide.currentIndex - 1].id);
  };
  const continueStep = async () => {
    if (lastStep) {
      if (completionMap.term_open) {
        await guide.finish();
        navigate("/admin/dashboard", { replace: true });
      }
      return;
    }
    await guide.advanceFrom(current.id);
  };
  const skipStep = async () => {
    await guide.skipStep(current.id);
    if (lastStep) navigate("/admin/dashboard", { replace: true });
  };

  const renderSessionStep = () => (
    <div className="space-y-5">
      {sessions.length ? (
        <div className="rounded-2xl border border-success/25 bg-success-soft/50 p-4">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
            <div>
              <p className="font-semibold text-text">Session available</p>
              <p className="mt-1 text-sm text-text-muted">
                {sessionLabel(selectedSession)} is ready for term configuration.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <form onSubmit={createSession} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Input
              label="Session name"
              value={sessionForm.name}
              placeholder="2026/2027"
              onChange={(event) =>
                setSessionForm((currentForm) => ({
                  ...currentForm,
                  name: event.target.value,
                }))
              }
              required
            />
          </div>
          <Input
            label="Start date"
            type="date"
            value={sessionForm.start_date}
            onChange={(event) =>
              setSessionForm((currentForm) => ({
                ...currentForm,
                start_date: event.target.value,
              }))
            }
            required
          />
          <Input
            label="End date"
            type="date"
            value={sessionForm.end_date}
            onChange={(event) =>
              setSessionForm((currentForm) => ({
                ...currentForm,
                end_date: event.target.value,
              }))
            }
            required
          />
          <div className="sm:col-span-2">
            <Button type="submit" disabled={saving === "session"} className="w-full sm:w-auto">
              {saving === "session" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarDays className="h-4 w-4" />}
              {saving === "session" ? "Creating session..." : "Create session"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );

  const renderTermStep = () => (
    <div className="space-y-5">
      {!selectedSession ? (
        <div className="rounded-2xl border border-warning/30 bg-warning-soft p-4 text-sm text-text-soft">
          A term must belong to a session. Return to the previous step or skip this step for now.
        </div>
      ) : termsForSession.length ? (
        <div className="rounded-2xl border border-success/25 bg-success-soft/50 p-4">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
            <div>
              <p className="font-semibold text-text">Term available</p>
              <p className="mt-1 text-sm text-text-muted">
                {termLabel(selectedTerm)} belongs to {sessionLabel(selectedSession)}.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <form onSubmit={createTerm} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <SearchableSelect
              label="Academic session"
              value={selectedSessionId}
              onChange={setSelectedSessionId}
              options={sessionOptions}
              searchable={sessions.length > 5}
              required
            />
          </div>
          <div className="sm:col-span-2">
            <SearchableSelect
              label="Term"
              value={termForm.name}
              onChange={(value) =>
                setTermForm((currentForm) => ({ ...currentForm, name: value }))
              }
              searchable={false}
              options={[
                { value: "first_term", label: "First term" },
                { value: "second_term", label: "Second term" },
                { value: "third_term", label: "Third term" },
              ]}
              required
            />
          </div>
          <Input
            label="Start date"
            type="date"
            value={termForm.start_date}
            onChange={(event) =>
              setTermForm((currentForm) => ({
                ...currentForm,
                start_date: event.target.value,
              }))
            }
            required
          />
          <Input
            label="End date"
            type="date"
            value={termForm.end_date}
            onChange={(event) =>
              setTermForm((currentForm) => ({
                ...currentForm,
                end_date: event.target.value,
              }))
            }
            required
          />
          <div className="sm:col-span-2">
            <Button type="submit" disabled={saving === "term"} className="w-full sm:w-auto">
              {saving === "term" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarCheck2 className="h-4 w-4" />}
              {saving === "term" ? "Creating term..." : "Create term"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );

  const renderCalendarStep = () => (
    <div className="space-y-5">
      {!selectedTerm ? (
        <div className="rounded-2xl border border-warning/30 bg-warning-soft p-4 text-sm text-text-soft">
          Create a term before generating its school calendar.
        </div>
      ) : calendarPrepared ? (
        <div className="rounded-2xl border border-success/25 bg-success-soft/50 p-4">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
            <div>
              <p className="font-semibold text-text">Calendar generated</p>
              <p className="mt-1 text-sm text-text-muted">
                The calendar for {termLabel(selectedTerm)} matches the current saved configuration and is ready for lifecycle checks.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <form onSubmit={generateCalendar} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <SearchableSelect
              label="Academic session"
              value={selectedSessionId}
              onChange={setSelectedSessionId}
              options={sessionOptions}
              searchable={sessions.length > 5}
              required
            />
            <SearchableSelect
              label="Academic term"
              value={selectedTerm?.id || ""}
              onChange={setSelectedTermId}
              options={termOptions}
              searchable={termsForSession.length > 5}
              required
            />
            <Input
              label="Timezone"
              value={calendarForm.timezone}
              onChange={(event) =>
                setCalendarForm((currentForm) => ({
                  ...currentForm,
                  timezone: event.target.value,
                }))
              }
              required
            />
            <div className="grid grid-cols-2 gap-3">
              <Input
                label="Opens"
                type="time"
                value={calendarForm.default_open_time}
                onChange={(event) =>
                  setCalendarForm((currentForm) => ({
                    ...currentForm,
                    default_open_time: event.target.value,
                  }))
                }
                required
              />
              <Input
                label="Closes"
                type="time"
                value={calendarForm.default_close_time}
                onChange={(event) =>
                  setCalendarForm((currentForm) => ({
                    ...currentForm,
                    default_close_time: event.target.value,
                  }))
                }
                required
              />
            </div>
          </div>
          <div className="rounded-xl border border-border bg-surface-muted/30 px-4 py-3 text-sm text-text-muted">
            The quick setup uses Monday to Friday as instructional days. You can refine holidays, events, and attendance rules later in the full calendar workspace.
          </div>
          <Button type="submit" disabled={saving === "calendar"} className="w-full sm:w-auto">
            {saving === "calendar" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarDays className="h-4 w-4" />}
            {saving === "calendar" ? "Preparing calendar..." : selectedCalendar ? "Save defaults and regenerate calendar" : "Save defaults and generate calendar"}
          </Button>
        </form>
      )}
    </div>
  );

  const renderStructureStep = () => (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-2xl border border-border bg-surface-muted/20 p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="font-semibold text-text">Classes</p>
            <p className="mt-1 text-sm text-text-muted">
              {classes.length ? `${classes.length} class${classes.length === 1 ? "" : "es"} available` : "Create the first class"}
            </p>
          </div>
          {classes.length ? <Badge variant="success">Ready</Badge> : null}
        </div>
        {!classes.length ? (
          <form onSubmit={createClass} className="mt-4 space-y-3">
            <Input
              label="Class name"
              value={classForm.name}
              placeholder="JSS 1"
              onChange={(event) =>
                setClassForm((currentForm) => ({
                  ...currentForm,
                  name: event.target.value,
                }))
              }
              required
            />
            <Input
              label="Arm"
              value={classForm.arm}
              placeholder="A"
              onChange={(event) =>
                setClassForm((currentForm) => ({
                  ...currentForm,
                  arm: event.target.value,
                }))
              }
            />
            <Button type="submit" disabled={saving === "class"} className="w-full">
              {saving === "class" ? <Loader2 className="h-4 w-4 animate-spin" /> : <School className="h-4 w-4" />}
              {saving === "class" ? "Creating..." : "Create class"}
            </Button>
          </form>
        ) : (
          <div className="mt-4 rounded-xl border border-success/20 bg-success-soft/40 px-3 py-3 text-sm text-text-soft">
            {classLabel(classes[0])} is available. More classes can be added later.
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-border bg-surface-muted/20 p-4 sm:p-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="font-semibold text-text">Subjects</p>
            <p className="mt-1 text-sm text-text-muted">
              {subjects.length ? `${subjects.length} subject${subjects.length === 1 ? "" : "s"} available` : "Create the first subject"}
            </p>
          </div>
          {subjects.length ? <Badge variant="success">Ready</Badge> : null}
        </div>
        {!subjects.length ? (
          <form onSubmit={createSubject} className="mt-4 space-y-3">
            <Input
              label="Subject name"
              value={subjectForm.name}
              placeholder="Mathematics"
              onChange={(event) =>
                setSubjectForm((currentForm) => ({
                  ...currentForm,
                  name: event.target.value,
                }))
              }
              required
            />
            <Input
              label="Subject code"
              value={subjectForm.code}
              placeholder="MTH"
              onChange={(event) =>
                setSubjectForm((currentForm) => ({
                  ...currentForm,
                  code: event.target.value,
                }))
              }
            />
            <Button type="submit" disabled={saving === "subject"} className="w-full">
              {saving === "subject" ? <Loader2 className="h-4 w-4 animate-spin" /> : <BookOpen className="h-4 w-4" />}
              {saving === "subject" ? "Creating..." : "Create subject"}
            </Button>
          </form>
        ) : (
          <div className="mt-4 rounded-xl border border-success/20 bg-success-soft/40 px-3 py-3 text-sm text-text-soft">
            {subjects[0]?.name || "A subject"} is available. More subjects can be added later.
          </div>
        )}
      </div>
    </div>
  );

  const renderSessionOpenStep = () => (
    <div className="space-y-4">
      <div className="rounded-2xl border border-primary/20 bg-primary-soft/35 p-4 sm:p-5">
        <p className="font-semibold text-text">Why the session opens first</p>
        <p className="mt-1 text-sm leading-6 text-text-muted">
          The backend requires the session to be open and current before it will allow calendar activation. Opening the session requires complete dates, at least one term, and saved calendar defaults.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <SetupCheck
          label="Draft session selected"
          complete={sessionDraft || sessionActive}
          detail={selectedSession ? `${sessionLabel(selectedSession)} · ${titleCase(selectedSession.status)}` : "No session selected"}
        />
        <SetupCheck
          label="Session dates complete"
          complete={sessionDatesComplete}
          detail={sessionDatesComplete ? `${selectedSession.start_date} to ${selectedSession.end_date}` : "Start and end dates are required"}
        />
        <SetupCheck
          label="At least one term exists"
          complete={Boolean(selectedTerm)}
          detail={selectedTerm ? termLabel(selectedTerm) : "Create a term in this session"}
        />
        <SetupCheck
          label="Calendar defaults saved"
          complete={Boolean(calendarConfiguration)}
          detail={calendarConfiguration ? "Configuration is available" : "Save calendar defaults first"}
        />
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-semibold text-text">Open {sessionLabel(selectedSession)}</p>
          <p className="mt-1 text-sm text-text-muted">
            This makes the session current. The term remains draft until the calendar is activated.
          </p>
        </div>
        <Button
          type="button"
          variant={sessionActive ? "outline" : "primary"}
          disabled={!sessionOpenReady || sessionActive || saving === "open-session"}
          onClick={openSession}
          className="w-full sm:w-auto"
        >
          {saving === "open-session" ? <Loader2 className="h-4 w-4 animate-spin" /> : <GraduationCap className="h-4 w-4" />}
          {sessionActive ? "Session open" : "Open session"}
        </Button>
      </div>
    </div>
  );

  const renderCalendarActivationStep = () => (
    <div className="space-y-4">
      <div className="rounded-2xl border border-primary/20 bg-primary-soft/35 p-4 sm:p-5">
        <p className="font-semibold text-text">Activate the calendar while the term is draft</p>
        <p className="mt-1 text-sm leading-6 text-text-muted">
          Calendar activation requires the selected session to be open and current, the term to remain draft, and every calendar date to pass the backend readiness checks.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <SetupCheck
          label="Session open and current"
          complete={sessionActive}
          detail={selectedSession ? `${sessionLabel(selectedSession)} · ${titleCase(selectedSession.status)}` : "Open the session first"}
        />
        <SetupCheck
          label="Term still draft"
          complete={termDraft || termActive}
          detail={selectedTerm ? `${termLabel(selectedTerm)} · ${titleCase(selectedTerm.status)}` : "No term selected"}
        />
        <SetupCheck
          label="Calendar generated and current"
          complete={calendarPrepared || calendarActive}
          detail={selectedCalendar ? `${titleCase(selectedCalendar.status)} calendar` : "Generate the calendar first"}
        />
        <SetupCheck
          label="Backend readiness passed"
          complete={calendarActive || (calendarPrepared && selectedCalendar?.can_activate !== false)}
          detail={calendarActive ? "Calendar is active" : calendarBlockers.length ? `${calendarBlockers.length} blocker${calendarBlockers.length === 1 ? "" : "s"} remain` : "No activation blockers"}
        />
      </div>

      {!calendarActive && calendarBlockers.length ? (
        <div className="rounded-2xl border border-warning/30 bg-warning-soft p-4">
          <p className="text-sm font-semibold text-text">Resolve these backend blockers</p>
          <ul className="mt-2 space-y-1.5 text-sm leading-6 text-text-muted">
            {calendarBlockers.map((blocker) => (
              <li key={blocker} className="flex gap-2">
                <span aria-hidden="true">•</span>
                <span>{blocker}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-semibold text-text">Activate {termLabel(selectedTerm)} calendar</p>
          <p className="mt-1 text-sm text-text-muted">
            Activation locks in the operational calendar required by term opening.
          </p>
        </div>
        <Button
          type="button"
          variant={calendarActive ? "outline" : "primary"}
          disabled={!calendarActivationReady || calendarActive || saving === "activate-calendar"}
          onClick={activateCalendar}
          className="w-full sm:w-auto"
        >
          {saving === "activate-calendar" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarCheck2 className="h-4 w-4" />}
          {calendarActive ? "Calendar active" : "Activate calendar"}
        </Button>
      </div>
    </div>
  );

  const renderTermOpenStep = () => (
    <div className="space-y-4">
      <div className="rounded-2xl border border-primary/20 bg-primary-soft/35 p-4 sm:p-5">
        <p className="font-semibold text-text">Open the term last</p>
        <p className="mt-1 text-sm leading-6 text-text-muted">
          The backend will open a draft term only when its parent session is open and current and its generated school calendar is active and complete.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <SetupCheck
          label="Session open and current"
          complete={sessionActive}
          detail={selectedSession ? sessionLabel(selectedSession) : "No session selected"}
        />
        <SetupCheck
          label="Calendar active"
          complete={calendarActive}
          detail={selectedCalendar ? titleCase(selectedCalendar.status) : "No calendar selected"}
        />
        <SetupCheck
          label="Term ready to open"
          complete={termDraft || termActive}
          detail={selectedTerm ? `${termLabel(selectedTerm)} · ${titleCase(selectedTerm.status)}` : "No term selected"}
        />
        <SetupCheck
          label="No other current term"
          complete={!anotherOpenTerm}
          detail={anotherOpenTerm ? `${termLabel(anotherOpenTerm)} is already open` : "No conflicting open term"}
        />
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-semibold text-text">Open {termLabel(selectedTerm)}</p>
          <p className="mt-1 text-sm text-text-muted">
            This is the final academic lifecycle transition in the setup assistant.
          </p>
        </div>
        <Button
          type="button"
          variant={termActive ? "outline" : "primary"}
          disabled={!termOpenReady || termActive || saving === "open-term"}
          onClick={openTerm}
          className="w-full sm:w-auto"
        >
          {saving === "open-term" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Clock3 className="h-4 w-4" />}
          {termActive ? "Term open" : "Open term"}
        </Button>
      </div>

      {termActive ? (
        <div className="rounded-2xl border border-success/25 bg-success-soft/50 p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
            <div>
              <p className="font-semibold text-text">Academic setup is active</p>
              <p className="mt-1 text-sm leading-6 text-text-muted">
                The session is current, the school calendar is active, and the term is open. The tenant can now continue from the Academic Hub.
              </p>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );

  const renderCurrentStep = () => {
    if (current.id === "session") return renderSessionStep();
    if (current.id === "term") return renderTermStep();
    if (current.id === "calendar") return renderCalendarStep();
    if (current.id === "structure") return renderStructureStep();
    if (current.id === "session_open") return renderSessionOpenStep();
    if (current.id === "calendar_active") return renderCalendarActivationStep();
    return renderTermOpenStep();
  };

  return (
    <DashboardLayout
      role="admin"
      title="School setup"
      description="Follow the backend-safe setup sequence without leaving the guided workspace."
      actions={(
        <Button
          type="button"
          size="small"
          variant="outline"
          onClick={() => loadSetup({ quiet: true })}
          disabled={refreshing}
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh status
        </Button>
      )}
    >
      <div className="space-y-5">
        <Card className="overflow-hidden border-primary/20 p-0">
          <div className="border-b border-border bg-primary-soft/45 px-4 py-5 sm:px-6 sm:py-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <div className="flex items-center gap-2 text-primary">
                  <Sparkles className="h-4 w-4" />
                  <p className="text-[11px] font-bold uppercase tracking-[0.16em]">
                    Guided academic launch
                  </p>
                </div>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-text sm:text-3xl">
                  Build the foundation, then run the school
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted sm:text-base">
                  The assistant verifies live records after every action. It does not cover the dashboard or prevent you from using other features.
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="small"
                onClick={() => navigate("/admin/dashboard")}
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

        {error ? (
          <div className="rounded-2xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-medium text-error">
            {error}
          </div>
        ) : null}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
          <Card className="p-4 sm:p-6">
            <StepHeading
              step={current}
              number={guide.currentIndex + 1}
              total={guide.steps.length}
              complete={currentComplete}
            />
            <div className="mt-6 border-t border-border pt-6">
              {renderCurrentStep()}
            </div>

            <div className="mt-7 flex flex-col-reverse gap-2 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
              <Button
                type="button"
                variant="ghost"
                disabled={firstStep}
                onClick={goPrevious}
              >
                <ArrowLeft className="h-4 w-4" />
                Previous
              </Button>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button type="button" variant="outline" onClick={skipStep}>
                  Skip this step
                </Button>
                <Button
                  type="button"
                  onClick={continueStep}
                  disabled={!currentComplete}
                >
                  {lastStep ? "Complete setup" : "Continue"}
                  {lastStep ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <ArrowRight className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          </Card>

          <div className="space-y-4">
            <Card className="p-4 sm:p-5">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-text-faint">
                Setup context
              </p>
              <div className="mt-4 space-y-3">
                <SearchableSelect
                  label="Session"
                  value={selectedSessionId}
                  onChange={setSelectedSessionId}
                  options={sessionOptions}
                  placeholder="No session yet"
                  searchable={sessions.length > 5}
                  clearable={false}
                  disabled={!sessions.length}
                />
                <SearchableSelect
                  label="Term"
                  value={selectedTerm?.id || ""}
                  onChange={setSelectedTermId}
                  options={termOptions}
                  placeholder="No term yet"
                  searchable={termsForSession.length > 5}
                  clearable={false}
                  disabled={!termsForSession.length}
                />
              </div>
            </Card>

            <Card className="p-4 sm:p-5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-text-faint">
                  Live status
                </p>
                <span className="text-sm font-bold text-primary">
                  {guide.completionPercent}%
                </span>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-muted">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-300"
                  style={{ width: `${guide.completionPercent}%` }}
                />
              </div>
              <div className="mt-4 space-y-2">
                <SetupCheck
                  label="Session created"
                  complete={completionMap.session}
                  detail={selectedSession ? sessionLabel(selectedSession) : "Waiting for a session"}
                />
                <SetupCheck
                  label="Term created"
                  complete={completionMap.term}
                  detail={selectedTerm ? termLabel(selectedTerm) : "Waiting for a term"}
                />
                <SetupCheck
                  label="Calendar prepared"
                  complete={completionMap.calendar}
                  detail={selectedCalendar ? titleCase(selectedCalendar.status) : "Waiting for a calendar"}
                />
                <SetupCheck
                  label="Classes and subjects"
                  complete={completionMap.structure}
                  detail={`${classes.length} classes · ${subjects.length} subjects`}
                />
                <SetupCheck
                  label="Session open"
                  complete={completionMap.session_open}
                  detail={sessionActive ? "Current academic session" : "Waiting for session opening"}
                />
                <SetupCheck
                  label="Calendar active"
                  complete={completionMap.calendar_active}
                  detail={calendarActive ? "Operational calendar active" : "Waiting for calendar activation"}
                />
                <SetupCheck
                  label="Term open"
                  complete={completionMap.term_open}
                  detail={termActive ? "Current academic term" : "Waiting for term opening"}
                />
              </div>
              <p className="mt-4 text-xs leading-5 text-text-faint">
                {calendarConfiguration
                  ? "Calendar defaults are saved."
                  : "Calendar defaults will be saved during the calendar step."}
              </p>
            </Card>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default AdminGettingStartedPage;
