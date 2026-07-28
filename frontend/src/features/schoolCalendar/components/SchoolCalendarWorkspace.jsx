import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarDays, RefreshCw, ShieldAlert } from "lucide-react";

import EmptyState from "../../../components/shared/EmptyState";
import LoadingState from "../../../components/shared/LoadingState";
import { getErrorMessage, isAbortError } from "../../../services/api";
import { academicService } from "../../../services/academicService";
import Badge from "../../../components/ui/Badge";
import Button from "../../../components/ui/Button";
import Input from "../../../components/ui/Input";
import {
  CheckboxControl,
  SelectControl,
  WorkspacePanel,
} from "../../academic-admin/AcademicWorkspacePrimitives";
import { schoolCalendarService } from "../api/schoolCalendarService";
import { dayTypeLabel, formatCalendarDate } from "../utils/calendarDisplay";
import CalendarEventCard from "./CalendarEventCard";
import CalendarStatusBadge from "./CalendarStatusBadge";

const asItems = (response) => (Array.isArray(response?.items) ? response.items : []);
const todayIso = () => new Date().toISOString().slice(0, 10);
const addDays = (isoDate, days) => {
  const date = new Date(`${isoDate}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
};

const formatTermName = (term) => String(term?.display_name || term?.name || "Term").replaceAll("_", " ");
const titleCase = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());

const calendarLabel = (calendar, sessions = [], terms = []) => {
  if (!calendar) return "Calendar";
  const session = sessions.find((item) => item.id === calendar.academic_session_id);
  const term = terms.find((item) => item.id === calendar.academic_term_id);
  const sessionName = session?.name || "Selected session";
  const termName = formatTermName(term);
  return `${sessionName} - ${termName} - ${titleCase(calendar.status || "draft")}`;
};

const generationResultMessage = (result) => {
  const created = Number(result?.generated_days_created || 0);
  const updated = Number(result?.generated_days_updated || 0);
  if (!created && !updated) return "No calendar days changed.";
  return `${result.total_days} total dates, ${result.instructional_days} instructional days, ${result.weekend_days} weekends, ${created} created, ${updated} updated, ${result.manual_days_preserved} manual overrides preserved.`;
};

function SchoolCalendarWorkspace({ activeTab = "manage" }) {
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [calendars, setCalendars] = useState([]);
  const [days, setDays] = useState([]);
  const [events, setEvents] = useState([]);
  const [configuration, setConfiguration] = useState(null);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [selectedTermId, setSelectedTermId] = useState("");
  const [selectedCalendarId, setSelectedCalendarId] = useState("");
  const [rangeStart, setRangeStart] = useState(todayIso());
  const [rangeEnd, setRangeEnd] = useState(addDays(todayIso(), 34));
  const [loading, setLoading] = useState(true);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [saving, setSaving] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [configForm, setConfigForm] = useState({
    timezone: "Africa/Lagos",
    instructional_weekdays: [0, 1, 2, 3, 4],
    default_open_time: "08:00",
    default_close_time: "15:00",
    default_student_attendance_required: true,
    default_workforce_attendance_required: true,
  });
  const [closureForm, setClosureForm] = useState({
    start_date: todayIso(),
    end_date: todayIso(),
    reason: "",
  });
  const [eventForm, setEventForm] = useState({
    title: "",
    description: "",
    event_type: "academic",
    audience: "all",
    is_all_day: false,
    starts_at: `${todayIso()}T08:00`,
    ends_at: `${todayIso()}T09:00`,
    location: "",
  });
  const [eventStatus, setEventStatus] = useState("");
  const [eventAudience, setEventAudience] = useState("");
  const [editingEventId, setEditingEventId] = useState("");
  const [editingDay, setEditingDay] = useState(null);
  const [dayForm, setDayForm] = useState({
    day_type: "instructional_day",
    title: "",
    description: "",
    school_open: true,
    student_activity_allowed: true,
    student_attendance_required: true,
    workforce_attendance_required: true,
    opens_at: "08:00",
    closes_at: "15:00",
    reason: "",
  });

  const selectedCalendar = calendars.find((item) => item.id === selectedCalendarId) || null;
  const selectedSession = sessions.find((item) => item.id === selectedSessionId) || null;
  const selectedTerm = terms.find((item) => item.id === selectedTermId) || null;
  const filteredTerms = useMemo(
    () => terms.filter((term) => !selectedSessionId || term.academic_session_id === selectedSessionId),
    [selectedSessionId, terms],
  );
  const filteredCalendars = useMemo(
    () => calendars.filter((calendar) => !selectedTermId || calendar.academic_term_id === selectedTermId),
    [calendars, selectedTermId],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const controller = new AbortController();
    try {
      const [sessionResponse, termResponse, calendarResponse, configResponse] = await Promise.all([
        academicService.listSessions({ limit: 100 }),
        academicService.listTerms({ limit: 100 }),
        schoolCalendarService.listAdminCalendars({ limit: 100 }, { signal: controller.signal }),
        schoolCalendarService.getConfiguration({ signal: controller.signal }).catch((err) => {
          if (err?.response?.status === 404) return null;
          throw err;
        }),
      ]);
      const sessionItems = asItems(sessionResponse);
      const termItems = asItems(termResponse);
      const calendarItems = asItems(calendarResponse);
      const currentSession = sessionItems.find((item) => item.is_current) || sessionItems.find((item) => item.status === "open") || null;
      const validTerms = termItems.filter((item) => !currentSession || item.academic_session_id === currentSession.id);
      const currentTerm = validTerms.find((item) => item.is_current) || validTerms.find((item) => item.status !== "closed") || validTerms[0] || null;
      const currentCalendar = calendarItems.find((item) => item.academic_term_id === currentTerm?.id) || null;

      setSessions(sessionItems);
      setTerms(termItems);
      setCalendars(calendarItems);
      setConfiguration(configResponse);
      setSelectedSessionId((value) => (sessionItems.some((item) => item.id === value) ? value : currentSession?.id || ""));
      setSelectedTermId((value) => {
        const term = termItems.find((item) => item.id === value);
        return term && (!currentSession || term.academic_session_id === currentSession.id) ? value : currentTerm?.id || "";
      });
      setSelectedCalendarId((value) => {
        const calendar = calendarItems.find((item) => item.id === value);
        return calendar && (!currentTerm || calendar.academic_term_id === currentTerm.id) ? value : currentCalendar?.id || "";
      });
      if (configResponse) {
        setConfigForm({
          timezone: configResponse.timezone || "Africa/Lagos",
          instructional_weekdays: configResponse.instructional_weekdays || [0, 1, 2, 3, 4],
          default_open_time: configResponse.default_open_time || "08:00",
          default_close_time: configResponse.default_close_time || "15:00",
          default_student_attendance_required: configResponse.default_student_attendance_required,
          default_workforce_attendance_required: configResponse.default_workforce_attendance_required,
        });
      }
    } catch (err) {
      if (!isAbortError(err)) setError(getErrorMessage(err, "Failed to load school calendar."));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCalendarDetails = useCallback(async () => {
    if (!selectedCalendarId) {
      setDays([]);
      setEvents([]);
      return;
    }
    setDetailsLoading(true);
    try {
      const [dayResponse, eventResponse] = await Promise.all([
        schoolCalendarService.getDays({
          calendar_id: selectedCalendarId,
          start_date: rangeStart,
          end_date: rangeEnd,
        }),
          schoolCalendarService.getAdminEvents({
          calendar_id: selectedCalendarId,
          start_date: rangeStart,
          end_date: rangeEnd,
          status: eventStatus || undefined,
          audience: eventAudience || undefined,
        }),
      ]);
      setDays(asItems(dayResponse));
      setEvents(asItems(eventResponse));
    } catch (err) {
      if (!isAbortError(err)) setError(getErrorMessage(err, "Failed to load calendar days."));
    } finally {
      setDetailsLoading(false);
    }
  }, [eventAudience, eventStatus, rangeEnd, rangeStart, selectedCalendarId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadCalendarDetails();
  }, [loadCalendarDetails]);

  useEffect(() => {
    if (!selectedSessionId) return;
    const term = terms.find((item) => item.id === selectedTermId);
    if (term && term.academic_session_id === selectedSessionId) return;
    const validTerms = terms.filter((item) => item.academic_session_id === selectedSessionId);
    const nextTerm = validTerms.find((item) => item.is_current) || validTerms.find((item) => item.status !== "closed") || validTerms[0] || null;
    setSelectedTermId(nextTerm?.id || "");
  }, [selectedSessionId, selectedTermId, terms]);

  useEffect(() => {
    if (!selectedTermId) {
      setSelectedCalendarId("");
      return;
    }
    const calendar = calendars.find((item) => item.id === selectedCalendarId);
    if (calendar && calendar.academic_term_id === selectedTermId) return;
    const nextCalendar = calendars.find((item) => item.academic_term_id === selectedTermId) || null;
    setSelectedCalendarId(nextCalendar?.id || "");
  }, [calendars, selectedCalendarId, selectedTermId]);

  const runAction = async (busyKey, action, success) => {
    setSaving(busyKey);
    setError("");
    setMessage("");
    try {
      const result = await action();
      setMessage(typeof success === "function" ? success(result) : success);
      await load();
      await loadCalendarDetails();
    } catch (err) {
      setError(getErrorMessage(err, "Calendar action failed."));
    } finally {
      setSaving("");
    }
  };

  const saveConfiguration = (event) => {
    event.preventDefault();
    runAction("configuration", () => schoolCalendarService.updateConfiguration(configForm), "Calendar configuration saved.");
  };

  const generateCalendar = () => {
    const isRegeneration = Boolean(selectedCalendar?.generated_at);
    if (isRegeneration) {
      const generatedDays = days.filter((day) => !day.is_manual_override).length;
      const manualOverrides = days.filter((day) => day.is_manual_override).length;
      const fromRevision = selectedCalendar.generated_from_configuration_revision || "none";
      const toRevision = configuration?.revision || "current";
      const confirmed = window.confirm(
        `Regenerate Calendar?\n\nGenerated days to update: ${generatedDays}\nManual overrides preserved: ${manualOverrides}\nConfiguration revision change: ${fromRevision} -> ${toRevision}`,
      );
      if (!confirmed) return;
    }
    runAction(
      "generate",
      () =>
        schoolCalendarService.generateCalendar({
          academic_session_id: selectedSessionId,
          academic_term_id: selectedTermId,
          overwrite_generated_days: isRegeneration,
        }),
      generationResultMessage,
    );
  };

  const createEmergencyClosure = (event) => {
    event.preventDefault();
    runAction(
      "closure",
      () =>
        schoolCalendarService.emergencyClosure({
          ...closureForm,
          calendar_id: selectedCalendarId || undefined,
        }),
      "Emergency closure applied.",
    );
  };

  const createEvent = (event) => {
    event.preventDefault();
    const eventPayload = {
      ...eventForm,
      starts_at: new Date(eventForm.starts_at).toISOString(),
      ends_at: new Date(eventForm.ends_at).toISOString(),
    };
    if (editingEventId) {
      runAction(
        "event",
        () => schoolCalendarService.updateEvent(editingEventId, eventPayload),
        "Calendar event updated.",
      ).then(() => setEditingEventId(""));
      return;
    }
    runAction(
      "event",
      () => schoolCalendarService.createEvent({ ...eventPayload, calendar_id: selectedCalendarId }),
      "Calendar event created as draft.",
    );
  };

  const startEventEdit = (item) => {
    setEditingEventId(item.id);
    setEventForm({
      title: item.title || "",
      description: item.description || "",
      event_type: item.event_type || "academic",
      audience: item.audience || "all",
      is_all_day: Boolean(item.is_all_day),
      starts_at: String(item.starts_at || "").slice(0, 16),
      ends_at: String(item.ends_at || "").slice(0, 16),
      location: item.location || "",
    });
  };

  const resetEventForm = () => {
    setEditingEventId("");
    setEventForm({
      title: "",
      description: "",
      event_type: "academic",
      audience: "all",
      is_all_day: false,
      starts_at: `${todayIso()}T08:00`,
      ends_at: `${todayIso()}T09:00`,
      location: "",
    });
  };

  const openDayEditor = (day) => {
    setEditingDay(day);
    setDayForm({
      day_type: day.day_type || "instructional_day",
      title: day.title || "",
      description: day.description || "",
      school_open: Boolean(day.school_open),
      student_activity_allowed: Boolean(day.student_activity_allowed),
      student_attendance_required: Boolean(day.student_attendance_required),
      workforce_attendance_required: Boolean(day.workforce_attendance_required),
      opens_at: day.opens_at || "",
      closes_at: day.closes_at || "",
      reason: "",
    });
  };

  const updateDay = (event) => {
    event.preventDefault();
    if (!editingDay) return;
    runAction(
      "day",
      () =>
        schoolCalendarService.updateDay(editingDay.calendar_date, {
          calendar_id: selectedCalendarId,
          ...dayForm,
          historical_correction_confirmed: Boolean(dayForm.reason),
        }),
      "Calendar day updated.",
    ).then(() => setEditingDay(null));
  };

  if (loading) return <LoadingState label="Loading school calendar..." />;

  const busy = Boolean(saving);

  return (
    <section className="space-y-4">
      {error ? <Notice tone="error" message={error} /> : null}
      {message ? <Notice tone="success" message={message} /> : null}

      {activeTab === "overview" ? (
        <OverviewTab
          selectedSession={selectedSession}
          selectedTerm={selectedTerm}
          selectedCalendar={selectedCalendar}
          configuration={configuration}
          events={events}
          days={days}
        />
      ) : null}

      {activeTab === "setup" ? (
        <SetupTab
          sessions={sessions}
          filteredTerms={filteredTerms}
          selectedSessionId={selectedSessionId}
          selectedTermId={selectedTermId}
          selectedSession={selectedSession}
          selectedTerm={selectedTerm}
          selectedCalendar={selectedCalendar}
          days={days}
          configForm={configForm}
          configuration={configuration}
          busy={busy}
          saving={saving}
          onSessionChange={setSelectedSessionId}
          onTermChange={setSelectedTermId}
          onConfigChange={setConfigForm}
          onSave={saveConfiguration}
          onGenerate={generateCalendar}
        />
      ) : null}

      {activeTab === "calendar" || activeTab === "manage" ? (
        <ManageTab
          calendars={filteredCalendars}
          sessions={sessions}
          terms={terms}
          days={days}
          detailsLoading={detailsLoading}
          selectedCalendar={selectedCalendar}
          selectedCalendarId={selectedCalendarId}
          rangeStart={rangeStart}
          rangeEnd={rangeEnd}
          busy={busy}
          onCalendarChange={setSelectedCalendarId}
          onRangeStartChange={setRangeStart}
          onRangeEndChange={setRangeEnd}
          onRefresh={loadCalendarDetails}
          onActivate={() =>
            runAction(
              "activate",
              () => schoolCalendarService.activateCalendar(selectedCalendar.id),
              "Calendar activated.",
            )
          }
          onArchive={() =>
            runAction(
              "archive",
              () =>
                schoolCalendarService.archiveCalendar(selectedCalendar.id, {
                  reason: "Calendar archived from admin workspace.",
                }),
              "Calendar archived.",
            )
          }
          onDayClick={openDayEditor}
        />
      ) : null}

      {activeTab === "events" ? (
        <EventsTab
          calendars={filteredCalendars}
          sessions={sessions}
          terms={terms}
          events={events}
          eventForm={eventForm}
          eventStatus={eventStatus}
          eventAudience={eventAudience}
          editingEventId={editingEventId}
          selectedCalendarId={selectedCalendarId}
          busy={busy}
          saving={saving}
          onCalendarChange={setSelectedCalendarId}
          onEventChange={setEventForm}
          onStatusChange={setEventStatus}
          onAudienceChange={setEventAudience}
          onCreate={createEvent}
          onEdit={startEventEdit}
          onCancelEdit={resetEventForm}
          onPublish={(eventId) =>
            runAction("event-action", () => schoolCalendarService.publishEvent(eventId), "Calendar event published.")
          }
          onCancel={(eventId) => {
            const reason = window.prompt("Reason for cancelling this event");
            if (!reason) return;
            runAction("event-action", () => schoolCalendarService.cancelEvent(eventId, reason), "Calendar event cancelled.");
          }}
        />
      ) : null}

      {activeTab === "closures" ? (
        <ClosuresTab
          calendars={filteredCalendars}
          sessions={sessions}
          terms={terms}
          closureForm={closureForm}
          selectedCalendarId={selectedCalendarId}
          busy={busy}
          saving={saving}
          onCalendarChange={setSelectedCalendarId}
          onClosureChange={setClosureForm}
          onCreate={createEmergencyClosure}
        />
      ) : null}

      {activeTab === "history" ? (
        <WorkspacePanel title="History" description="Lifecycle audit history will appear here once the backend exposes a read endpoint.">
          <p className="text-sm text-text-muted">Calendar mutations are already written to audit records on configuration, generation, activation, archival, day, range, closure, and event actions.</p>
        </WorkspacePanel>
      ) : null}

      {editingDay ? (
        <DayEditor
          day={editingDay}
          form={dayForm}
          busy={busy}
          saving={saving}
          onChange={setDayForm}
          onClose={() => setEditingDay(null)}
          onSubmit={updateDay}
        />
      ) : null}
    </section>
  );
}

function SetupTab({
  sessions,
  filteredTerms,
  selectedSessionId,
  selectedTermId,
  selectedSession,
  selectedTerm,
  selectedCalendar,
  days,
  configForm,
  configuration,
  busy,
  saving,
  onSessionChange,
  onTermChange,
  onConfigChange,
  onSave,
  onGenerate,
}) {
  const setupSteps = [
    ["Select session and term", selectedSessionId && selectedTermId],
    ["Validate term dates", selectedTerm?.start_date && selectedTerm?.end_date],
    ["Configure normal operating pattern", Boolean(configuration)],
    ["Generate preview", Boolean(selectedTermId)],
    ["Review generated dates", false],
    ["Add holidays and exceptions", false],
    ["Activate calendar", false],
    ["Open term", selectedCalendar?.status === "active"],
  ];
  const isRegeneration = Boolean(selectedCalendar?.generated_at);
  const generatedDays = days.filter((day) => !day.is_manual_override).length;
  const manualOverrides = days.filter((day) => day.is_manual_override).length;

  return (
    <WorkspacePanel title="Calendar Setup">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.85fr)]">
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <SelectControl
              label="Session"
              value={selectedSessionId}
              onChange={onSessionChange}
              options={sessions.map((session) => ({ value: session.id, label: session.name }))}
            />
            <SelectControl
              label="Term"
              value={selectedTermId}
              onChange={onTermChange}
              options={filteredTerms.map((term) => ({ value: term.id, label: String(term.display_name || term.name).replaceAll("_", " ") }))}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <Metric label="Session" value={selectedSession?.name || "Not selected"} />
            <Metric label="Term" value={formatTermName(selectedTerm)} />
            <Metric label="Calendar" value={titleCase(selectedCalendar?.status || "Not generated")} />
          </div>

          <div className="grid gap-2 sm:grid-cols-4">
            {setupSteps.map(([label, complete], index) => {
              const current = !complete && setupSteps.slice(0, index).every(([, done]) => done);
              return (
                <div key={label} className="rounded-lg border border-border/70 bg-surface px-3 py-2">
                  <p className="text-xs font-semibold text-text">{index + 1}. {label}</p>
                  <Badge className="mt-2" variant={complete ? "success" : current ? "warning" : "default"}>
                    {complete ? "complete" : current ? "current" : "not started"}
                  </Badge>
                </div>
              );
            })}
          </div>

          {isRegeneration ? (
            <div className="rounded-lg border border-warning/40 bg-warning-soft px-3 py-3 text-sm font-medium text-amber-950">
              Regeneration will update {generatedDays} generated day{generatedDays === 1 ? "" : "s"}, preserve {manualOverrides} manual override{manualOverrides === 1 ? "" : "s"}, and move revision {selectedCalendar.generated_from_configuration_revision || "none"} to {configuration?.revision || "current"} after confirmation.
            </div>
          ) : null}

          <Button type="button" onClick={onGenerate} disabled={busy || !selectedSessionId || !selectedTermId}>
            <RefreshCw className="h-4 w-4" />
            {saving === "generate" ? "Generating..." : isRegeneration ? "Regenerate Calendar" : "Generate Calendar"}
          </Button>
        </div>

        <form className="space-y-4" onSubmit={onSave}>
          <Input label="Timezone" value={configForm.timezone || ""} onChange={(event) => onConfigChange((current) => ({ ...current, timezone: event.target.value }))} />
          <WeekdayPicker
            value={configForm.instructional_weekdays}
            onChange={(instructional_weekdays) => onConfigChange((current) => ({ ...current, instructional_weekdays }))}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Opens at" type="time" value={configForm.default_open_time || ""} onChange={(event) => onConfigChange((current) => ({ ...current, default_open_time: event.target.value }))} />
            <Input label="Closes at" type="time" value={configForm.default_close_time || ""} onChange={(event) => onConfigChange((current) => ({ ...current, default_close_time: event.target.value }))} />
          </div>
          <CheckboxControl label="Students expected on open days" checked={configForm.default_student_attendance_required} onChange={(value) => onConfigChange((current) => ({ ...current, default_student_attendance_required: value }))} />
          <CheckboxControl label="Workforce expected on open days" checked={configForm.default_workforce_attendance_required} onChange={(value) => onConfigChange((current) => ({ ...current, default_workforce_attendance_required: value }))} />
          <Button type="submit" disabled={busy}>
            {saving === "configuration" ? "Saving..." : configuration ? "Save Configuration" : "Create Configuration"}
          </Button>
        </form>
      </div>
    </WorkspacePanel>
  );
}

function OverviewTab({ selectedSession, selectedTerm, selectedCalendar, configuration, events, days }) {
  const missingDates = Number(selectedCalendar?.missing_dates || selectedCalendar?.dependency_counts?.missing_dates || 0);
  const invalidDays = Number(selectedCalendar?.invalid_days || selectedCalendar?.dependency_counts?.invalid_days || 0);
  const manualOverrides = days.filter((day) => day.is_manual_override).length;
  const coverageTotal = Number(selectedCalendar?.dependency_counts?.days || days.length || 0) + missingDates;
  const coverage = coverageTotal ? Math.round(((coverageTotal - missingDates) / coverageTotal) * 100) : 0;
  const nextAction = !configuration
    ? "Create configuration"
    : !selectedCalendar
      ? "Generate preview"
      : selectedCalendar.configuration_outdated
        ? "Regenerate generated dates"
        : selectedCalendar.can_activate
          ? "Activate calendar"
          : selectedTerm?.status === "draft" && selectedCalendar.status === "active"
            ? "Open term"
            : "Review blockers";

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)]">
      <WorkspacePanel title="Calendar Overview" description="Operational readiness for the selected session and term.">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <Metric label="Selected session" value={selectedSession?.name || "No session selected"} />
          <Metric label="Selected term" value={formatTermName(selectedTerm)} />
          <Metric label="Calendar label" value={selectedCalendar ? calendarLabel(selectedCalendar, selectedSession ? [selectedSession] : [], selectedTerm ? [selectedTerm] : []) : "No calendar"} />
          <Metric label="Session status" value={titleCase(selectedSession?.status || "unknown")} />
          <Metric label="Term status" value={titleCase(selectedTerm?.status || "unknown")} />
          <Metric label="Calendar status" value={titleCase(selectedCalendar?.status || "not generated")} />
          <Metric label="Configuration status" value={configuration ? `Revision ${configuration.revision}` : "No configuration"} />
          <Metric label="Coverage" value={`${coverage}%`} />
          <Metric label="Missing dates" value={missingDates} />
          <Metric label="Invalid dates" value={invalidDays} />
          <Metric label="Manual overrides" value={manualOverrides} />
          <Metric label="Upcoming events" value={events.length} />
        </div>
      </WorkspacePanel>
      <WorkspacePanel title="Next Required Action" description="Resolve blockers in order before opening the term.">
        <p className="text-lg font-semibold text-text">{nextAction}</p>
        <div className="mt-4 space-y-2">
          {selectedCalendar?.blocker_messages?.length ? (
            selectedCalendar.blocker_messages.map((message) => (
              <div key={message} className="rounded-xl border border-warning/30 bg-warning-soft px-3 py-2 text-sm font-medium text-amber-950">
                {message}
              </div>
            ))
          ) : (
            <p className="text-sm text-text-muted">No blockers reported for the selected calendar.</p>
          )}
        </div>
      </WorkspacePanel>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-xl border border-border/70 bg-surface px-3 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-text">{value}</p>
    </div>
  );
}

function ManageTab({
  calendars,
  sessions,
  terms,
  days,
  detailsLoading,
  selectedCalendar,
  selectedCalendarId,
  rangeStart,
  rangeEnd,
  busy,
  onCalendarChange,
  onRangeStartChange,
  onRangeEndChange,
  onRefresh,
  onActivate,
  onArchive,
  onDayClick,
}) {
  return (
    <div className="space-y-4">
      <WorkspacePanel title="Calendar">
        {!selectedCalendar ? (
          <EmptyState icon={CalendarDays} title="No calendar generated" />
        ) : (
          <div className="space-y-4">
            <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
              <SelectControl
                label="Calendar"
                value={selectedCalendarId}
                onChange={onCalendarChange}
                options={calendars.map((calendar) => ({
                  value: calendar.id,
                  label: calendarLabel(calendar, sessions, terms),
                }))}
              />
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="small" variant="outline" onClick={onRefresh} disabled={busy || detailsLoading}>
                  <RefreshCw className="h-4 w-4" />
                  Refresh
                </Button>
                <Button type="button" size="small" onClick={onActivate} disabled={busy || !selectedCalendar.can_activate}>
                  Activate
                </Button>
                <Button type="button" size="small" variant="outline" onClick={onArchive} disabled={busy || !selectedCalendar.can_archive}>
                  Archive
                </Button>
              </div>
            </div>

            <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.45fr)]">
              <div className="rounded-lg border border-border/70 bg-surface px-3 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <CalendarStatusBadge status={selectedCalendar.status} />
                  {selectedCalendar.can_activate ? <Badge variant="warning">Activation ready</Badge> : null}
                  {selectedCalendar.can_archive ? <Badge variant="default">Archive available</Badge> : null}
                  {selectedCalendar.configuration_outdated ? <Badge variant="warning">Configuration outdated</Badge> : null}
                </div>
                <p className="mt-3 text-sm text-text-muted">
                  {selectedCalendar.blocker_messages?.length
                    ? selectedCalendar.blocker_messages.join(" ")
                    : "No lifecycle blockers reported."}
                </p>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <Metric label="Days" value={selectedCalendar.dependency_counts?.days || days.length} />
                <Metric label="Missing" value={selectedCalendar.missing_dates || 0} />
                <Metric label="Invalid" value={selectedCalendar.invalid_days || 0} />
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-[minmax(10rem,1fr)_minmax(10rem,1fr)] lg:max-w-xl">
              <Input label="Start" type="date" value={rangeStart} onChange={(event) => onRangeStartChange(event.target.value)} />
              <Input label="End" type="date" value={rangeEnd} onChange={(event) => onRangeEndChange(event.target.value)} />
            </div>

            {detailsLoading ? <LoadingState label="Loading generated days..." /> : <CalendarMonthView days={days} onDayClick={onDayClick} />}
          </div>
        )}
      </WorkspacePanel>
    </div>
  );
}

function EventsTab({
  calendars,
  sessions,
  terms,
  events,
  eventForm,
  eventStatus,
  eventAudience,
  editingEventId,
  selectedCalendarId,
  busy,
  saving,
  onCalendarChange,
  onEventChange,
  onStatusChange,
  onAudienceChange,
  onCreate,
  onEdit,
  onCancelEdit,
  onPublish,
  onCancel,
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(20rem,0.85fr)_minmax(0,1.35fr)]">
      <WorkspacePanel title={editingEventId ? "Edit Event" : "Create Event"} description="Create or edit calendar events for the selected generated calendar.">
        <form className="space-y-4" onSubmit={onCreate}>
          <SelectControl
            label="Calendar"
            value={selectedCalendarId}
            onChange={onCalendarChange}
            options={calendars.map((calendar) => ({ value: calendar.id, label: calendarLabel(calendar, sessions, terms) }))}
          />
          <Input label="Title" value={eventForm.title} onChange={(event) => onEventChange((current) => ({ ...current, title: event.target.value }))} />
          <Input label="Description" value={eventForm.description} onChange={(event) => onEventChange((current) => ({ ...current, description: event.target.value }))} />
          <SelectControl label="Event type" value={eventForm.event_type} onChange={(value) => onEventChange((current) => ({ ...current, event_type: value }))} options={["academic", "holiday", "examination", "meeting", "activity", "emergency", "other"].map((value) => ({ value, label: value.replaceAll("_", " ") }))} />
          <SelectControl label="Audience" value={eventForm.audience} onChange={(value) => onEventChange((current) => ({ ...current, audience: value }))} options={["all", "tenant_admins", "teachers", "parents", "students"].map((value) => ({ value, label: value.replaceAll("_", " ") }))} />
          <CheckboxControl label="All-day event" checked={eventForm.is_all_day} onChange={(value) => onEventChange((current) => ({ ...current, is_all_day: value }))} />
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Starts" type="datetime-local" value={eventForm.starts_at} onChange={(event) => onEventChange((current) => ({ ...current, starts_at: event.target.value }))} />
            <Input label="Ends" type="datetime-local" value={eventForm.ends_at} onChange={(event) => onEventChange((current) => ({ ...current, ends_at: event.target.value }))} />
          </div>
          <Input label="Location" value={eventForm.location} onChange={(event) => onEventChange((current) => ({ ...current, location: event.target.value }))} />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={busy || !selectedCalendarId || !eventForm.title}>
              {saving === "event" ? "Saving..." : editingEventId ? "Save Event" : "Add Event"}
            </Button>
            {editingEventId ? <Button type="button" variant="outline" onClick={onCancelEdit} disabled={busy}>Cancel Edit</Button> : null}
          </div>
        </form>
      </WorkspacePanel>

      <WorkspacePanel title="Event List" description="Review events in the currently selected calendar range.">
        <div className="mb-4 grid gap-3 sm:grid-cols-2">
          <SelectControl
            label="Status"
            value={eventStatus}
            onChange={onStatusChange}
            options={[
              { value: "", label: "All statuses" },
              { value: "draft", label: "Draft" },
              { value: "published", label: "Published" },
              { value: "cancelled", label: "Cancelled" },
            ]}
          />
          <SelectControl
            label="Audience"
            value={eventAudience}
            onChange={onAudienceChange}
            options={[
              { value: "", label: "All audiences" },
              { value: "all", label: "All" },
              { value: "tenant_admins", label: "Admins" },
              { value: "teachers", label: "Teachers" },
              { value: "parents", label: "Parents" },
              { value: "students", label: "Students" },
            ]}
          />
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          {events.length ? events.map((event) => (
            <div key={event.id} className="space-y-2">
              <CalendarEventCard event={event} compact />
              <div className="flex flex-wrap gap-2">
                {event.status !== "cancelled" ? <Button type="button" size="small" variant="outline" onClick={() => onEdit(event)} disabled={busy}>Edit</Button> : null}
                {event.status === "draft" ? <Button type="button" size="small" onClick={() => onPublish(event.id)} disabled={busy}>Publish</Button> : null}
                {event.status !== "cancelled" ? <Button type="button" size="small" variant="outline" onClick={() => onCancel(event.id)} disabled={busy}>Cancel</Button> : null}
              </div>
            </div>
          )) : <p className="text-sm text-text-muted">No events in this range.</p>}
        </div>
      </WorkspacePanel>
    </div>
  );
}

function ClosuresTab({
  calendars,
  sessions,
  terms,
  closureForm,
  selectedCalendarId,
  busy,
  saving,
  onCalendarChange,
  onClosureChange,
  onCreate,
}) {
  return (
    <WorkspacePanel title="Emergency Closure" description="Mark a date range closed when the school must suspend normal operations.">
      <form className="max-w-3xl space-y-4" onSubmit={onCreate}>
        <SelectControl
          label="Calendar"
          value={selectedCalendarId}
          onChange={onCalendarChange}
          options={calendars.map((calendar) => ({ value: calendar.id, label: calendarLabel(calendar, sessions, terms) }))}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <Input label="Start date" type="date" value={closureForm.start_date} onChange={(event) => onClosureChange((current) => ({ ...current, start_date: event.target.value }))} />
          <Input label="End date" type="date" value={closureForm.end_date} onChange={(event) => onClosureChange((current) => ({ ...current, end_date: event.target.value }))} />
        </div>
        <Input label="Reason" value={closureForm.reason} onChange={(event) => onClosureChange((current) => ({ ...current, reason: event.target.value }))} />
        <div className="rounded-2xl border border-warning/40 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-950">
          School operations will be marked closed for these dates. Student activities will be disabled.
        </div>
        <Button type="submit" variant="danger" disabled={busy || !selectedCalendarId || !closureForm.reason}>
          <ShieldAlert className="h-4 w-4" />
          {saving === "closure" ? "Applying..." : "Create Emergency Closure"}
        </Button>
      </form>
    </WorkspacePanel>
  );
}

function WeekdayPicker({ value = [], onChange }) {
  const labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const toggle = (index) => {
    const next = value.includes(index)
      ? value.filter((item) => item !== index)
      : [...value, index].sort();
    onChange(next);
  };
  return (
    <div>
      <p className="mb-2 text-sm font-semibold text-text-soft">Operating weekdays</p>
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
        {labels.map((label, index) => (
          <button
            key={label}
            type="button"
            onClick={() => toggle(index)}
            className={`min-h-10 rounded-xl border text-xs font-semibold ${value.includes(index) ? "border-primary bg-primary text-white" : "border-border/70 bg-surface text-text-soft"}`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function CalendarMonthView({ days, onDayClick }) {
  if (!days.length) {
    return <EmptyState icon={CalendarDays} title="No days in range" />;
  }
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
      {days.map((day) => (
        <button key={day.id} type="button" onClick={() => onDayClick(day)} className="min-h-24 rounded-lg border border-border/70 bg-surface px-3 py-3 text-left transition hover:border-primary/50">
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-semibold text-text">{formatCalendarDate(day.calendar_date)}</p>
            <CalendarStatusBadge status={day.school_open ? "active" : "closed"}>
              {day.school_open ? "Open" : "Closed"}
            </CalendarStatusBadge>
          </div>
          <p className="mt-3 text-xs font-semibold text-text-soft">{dayTypeLabel(day.day_type)}</p>
          {day.title ? <p className="mt-1 line-clamp-2 text-xs text-text-muted">{day.title}</p> : null}
        </button>
      ))}
    </div>
  );
}

function DayEditor({ day, form, busy, saving, onChange, onClose, onSubmit }) {
  const applyPreset = (preset) => {
    const presets = {
      public_holiday: { day_type: "public_holiday", school_open: false, student_activity_allowed: false, student_attendance_required: false, workforce_attendance_required: false, title: "Public holiday", opens_at: "", closes_at: "" },
      school_holiday: { day_type: "school_holiday", school_open: false, student_activity_allowed: false, student_attendance_required: false, workforce_attendance_required: false, title: "School holiday", opens_at: "", closes_at: "" },
      examination_day: { day_type: "examination_day", school_open: true, student_activity_allowed: true, student_attendance_required: true, workforce_attendance_required: true, title: "Examination day" },
      special_school_day: { day_type: "special_school_day", school_open: true, student_activity_allowed: true, student_attendance_required: true, workforce_attendance_required: true, title: "Special school day" },
      staff_training_day: { day_type: "staff_training_day", school_open: true, student_activity_allowed: false, student_attendance_required: false, workforce_attendance_required: true, title: "Staff training day" },
      weekend_school_day: { day_type: "special_school_day", school_open: true, student_activity_allowed: true, student_attendance_required: true, workforce_attendance_required: true, title: "Weekend school day" },
    };
    onChange((current) => ({ ...current, ...presets[preset] }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end bg-black/30 px-3 py-3 sm:items-center sm:justify-center">
      <form className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-border bg-surface p-4 shadow-xl sm:p-5" onSubmit={onSubmit}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Calendar day</p>
            <h3 className="mt-1 text-lg font-semibold text-text">{formatCalendarDate(day.calendar_date, { year: "numeric" })}</h3>
          </div>
          <Button type="button" size="small" variant="outline" onClick={onClose} disabled={busy}>Close</Button>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {[
            ["public_holiday", "Public holiday"],
            ["school_holiday", "School holiday"],
            ["examination_day", "Examination day"],
            ["special_school_day", "Special day"],
            ["staff_training_day", "Staff training"],
            ["weekend_school_day", "Weekend open"],
          ].map(([value, label]) => (
            <Button key={value} type="button" size="small" variant="outline" onClick={() => applyPreset(value)}>{label}</Button>
          ))}
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <SelectControl label="Day type" value={form.day_type} onChange={(value) => onChange((current) => ({ ...current, day_type: value }))} options={["instructional_day", "examination_day", "weekend", "public_holiday", "school_holiday", "mid_term_break", "staff_training_day", "special_school_day", "emergency_closure"].map((value) => ({ value, label: value.replaceAll("_", " ") }))} />
          <Input label="Title" value={form.title} onChange={(event) => onChange((current) => ({ ...current, title: event.target.value }))} />
          <Input label="Opens at" type="time" value={form.opens_at || ""} onChange={(event) => onChange((current) => ({ ...current, opens_at: event.target.value }))} />
          <Input label="Closes at" type="time" value={form.closes_at || ""} onChange={(event) => onChange((current) => ({ ...current, closes_at: event.target.value }))} />
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <CheckboxControl label="School open" checked={form.school_open} onChange={(value) => onChange((current) => ({ ...current, school_open: value }))} />
          <CheckboxControl label="Student activity allowed" checked={form.student_activity_allowed} onChange={(value) => onChange((current) => ({ ...current, student_activity_allowed: value }))} />
          <CheckboxControl label="Student operational expectation" checked={form.student_attendance_required} onChange={(value) => onChange((current) => ({ ...current, student_attendance_required: value }))} />
          <CheckboxControl label="Workforce operational expectation" checked={form.workforce_attendance_required} onChange={(value) => onChange((current) => ({ ...current, workforce_attendance_required: value }))} />
        </div>
        <div className="mt-4 space-y-3">
          <Input label="Description" value={form.description} onChange={(event) => onChange((current) => ({ ...current, description: event.target.value }))} />
          <Input label="Reason" value={form.reason} onChange={(event) => onChange((current) => ({ ...current, reason: event.target.value }))} />
        </div>
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button type="submit" disabled={busy}>{saving === "day" ? "Saving..." : "Save Day"}</Button>
        </div>
      </form>
    </div>
  );
}

function Notice({ tone, message }) {
  const className =
    tone === "success"
      ? "border-success/30 bg-success-soft text-success"
      : "border-error/30 bg-error-soft text-error";
  return <div className={`rounded-2xl border px-4 py-3 text-sm font-medium ${className}`}>{message}</div>;
}

export default SchoolCalendarWorkspace;
