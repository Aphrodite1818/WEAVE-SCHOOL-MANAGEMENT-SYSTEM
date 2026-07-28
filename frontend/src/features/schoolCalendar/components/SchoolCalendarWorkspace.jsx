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

const calendarLabel = (calendar) => {
  if (!calendar) return "Calendar";
  const status = String(calendar.status || "draft").replaceAll("_", " ");
  return `${status} / ${String(calendar.academic_term_id || calendar.id).slice(0, 8)}`;
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
    event_type: "academic",
    audience: "all",
    starts_at: `${todayIso()}T08:00`,
    ends_at: `${todayIso()}T09:00`,
  });

  const selectedCalendar = calendars.find((item) => item.id === selectedCalendarId) || null;
  const selectedSession = sessions.find((item) => item.id === selectedSessionId) || null;
  const selectedTerm = terms.find((item) => item.id === selectedTermId) || null;
  const filteredTerms = useMemo(
    () => terms.filter((term) => !selectedSessionId || term.academic_session_id === selectedSessionId),
    [selectedSessionId, terms],
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
      const currentSession = sessionItems.find((item) => item.is_current) || sessionItems[0] || null;
      const currentTerm = termItems.find((item) => item.is_current) || termItems[0] || null;
      const currentCalendar =
        calendarItems.find((item) => item.academic_term_id === currentTerm?.id) || calendarItems[0] || null;

      setSessions(sessionItems);
      setTerms(termItems);
      setCalendars(calendarItems);
      setConfiguration(configResponse);
      setSelectedSessionId((value) => value || currentSession?.id || "");
      setSelectedTermId((value) => value || currentTerm?.id || "");
      setSelectedCalendarId((value) => value || currentCalendar?.id || "");
      if (configResponse) {
        setConfigForm({
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
        schoolCalendarService.getEvents({
          calendar_id: selectedCalendarId,
          start_date: rangeStart,
          end_date: rangeEnd,
        }),
      ]);
      setDays(asItems(dayResponse));
      setEvents(asItems(eventResponse));
    } catch (err) {
      if (!isAbortError(err)) setError(getErrorMessage(err, "Failed to load calendar days."));
    } finally {
      setDetailsLoading(false);
    }
  }, [rangeEnd, rangeStart, selectedCalendarId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadCalendarDetails();
  }, [loadCalendarDetails]);

  const runAction = async (busyKey, action, success) => {
    setSaving(busyKey);
    setError("");
    setMessage("");
    try {
      await action();
      setMessage(success);
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
    runAction(
      "generate",
      () =>
        schoolCalendarService.generateCalendar({
          academic_session_id: selectedSessionId,
          academic_term_id: selectedTermId,
          overwrite_generated_days: false,
        }),
      "Calendar generated.",
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
    runAction(
      "event",
      () =>
        schoolCalendarService.createEvent({
          ...eventForm,
          calendar_id: selectedCalendarId,
          starts_at: new Date(eventForm.starts_at).toISOString(),
          ends_at: new Date(eventForm.ends_at).toISOString(),
        }),
      "Calendar event created as draft.",
    );
  };

  if (loading) return <LoadingState label="Loading school calendar..." />;

  const busy = Boolean(saving);

  return (
    <section className="space-y-4">
      {error ? <Notice tone="error" message={error} /> : null}
      {message ? <Notice tone="success" message={message} /> : null}

      {activeTab === "setup" ? (
        <SetupTab
          sessions={sessions}
          filteredTerms={filteredTerms}
          selectedSessionId={selectedSessionId}
          selectedTermId={selectedTermId}
          selectedSession={selectedSession}
          selectedTerm={selectedTerm}
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

      {activeTab === "manage" ? (
        <ManageTab
          calendars={calendars}
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
        />
      ) : null}

      {activeTab === "events" ? (
        <EventsTab
          calendars={calendars}
          events={events}
          eventForm={eventForm}
          selectedCalendarId={selectedCalendarId}
          busy={busy}
          saving={saving}
          onCalendarChange={setSelectedCalendarId}
          onEventChange={setEventForm}
          onCreate={createEvent}
        />
      ) : null}

      {activeTab === "closures" ? (
        <ClosuresTab
          calendars={calendars}
          closureForm={closureForm}
          selectedCalendarId={selectedCalendarId}
          busy={busy}
          saving={saving}
          onCalendarChange={setSelectedCalendarId}
          onClosureChange={setClosureForm}
          onCreate={createEmergencyClosure}
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
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(20rem,0.9fr)]">
      <WorkspacePanel title="Operating Pattern" description="Set the normal school week and default attendance expectations before generation.">
        <form className="space-y-4" onSubmit={onSave}>
          <WeekdayPicker
            value={configForm.instructional_weekdays}
            onChange={(instructional_weekdays) => onConfigChange((current) => ({ ...current, instructional_weekdays }))}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Opens at" type="time" value={configForm.default_open_time || ""} onChange={(event) => onConfigChange((current) => ({ ...current, default_open_time: event.target.value }))} />
            <Input label="Closes at" type="time" value={configForm.default_close_time || ""} onChange={(event) => onConfigChange((current) => ({ ...current, default_close_time: event.target.value }))} />
          </div>
          <CheckboxControl label="Student attendance expected on normal open days" checked={configForm.default_student_attendance_required} onChange={(value) => onConfigChange((current) => ({ ...current, default_student_attendance_required: value }))} />
          <CheckboxControl label="Workforce attendance expected on normal open days" checked={configForm.default_workforce_attendance_required} onChange={(value) => onConfigChange((current) => ({ ...current, default_workforce_attendance_required: value }))} />
          <Button type="submit" disabled={busy}>
            {saving === "configuration" ? "Saving..." : configuration ? "Save Configuration" : "Create Configuration"}
          </Button>
        </form>
      </WorkspacePanel>

      <WorkspacePanel title="Generate Term Calendar" description="Choose the session and term, then generate the working calendar from the saved operating pattern.">
        <div className="space-y-4">
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
          <div className="rounded-2xl border border-border/70 bg-surface-muted/30 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Selected scope</p>
            <p className="mt-2 text-sm font-semibold text-text">{selectedSession?.name || "No session selected"}</p>
            <p className="mt-1 text-sm text-text-muted">{selectedTerm?.display_name || selectedTerm?.name || "No term selected"}</p>
          </div>
          <Button type="button" onClick={onGenerate} disabled={busy || !selectedSessionId || !selectedTermId}>
            <RefreshCw className="h-4 w-4" />
            {saving === "generate" ? "Generating..." : "Generate Calendar"}
          </Button>
        </div>
      </WorkspacePanel>
    </div>
  );
}

function ManageTab({
  calendars,
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
}) {
  return (
    <div className="space-y-4">
      <WorkspacePanel
        title="Calendar Review"
        description="Review generated days and keep lifecycle actions grouped with the selected calendar."
        actions={
          <SelectControl
            label="Calendar"
            value={selectedCalendarId}
            onChange={onCalendarChange}
            options={calendars.map((calendar) => ({
              value: calendar.id,
              label: calendarLabel(calendar),
            }))}
          />
        }
      >
        {!selectedCalendar ? (
          <EmptyState icon={CalendarDays} title="No calendar generated" />
        ) : (
          <div className="space-y-4">
            <div className="flex flex-col gap-4 rounded-2xl border border-border/70 bg-surface-muted/30 px-4 py-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <CalendarStatusBadge status={selectedCalendar.status} />
                  {selectedCalendar.can_activate ? <Badge variant="warning">Activation ready</Badge> : null}
                  {selectedCalendar.can_archive ? <Badge variant="default">Archive available</Badge> : null}
                </div>
                <p className="mt-3 text-sm text-text-muted">
                  {selectedCalendar.blocker_messages?.length
                    ? selectedCalendar.blocker_messages.join(" ")
                    : "No lifecycle blockers reported."}
                </p>
              </div>
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

            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="Start" type="date" value={rangeStart} onChange={(event) => onRangeStartChange(event.target.value)} />
              <Input label="End" type="date" value={rangeEnd} onChange={(event) => onRangeEndChange(event.target.value)} />
            </div>

            {detailsLoading ? <LoadingState label="Loading generated days..." /> : <CalendarMonthView days={days} />}
          </div>
        )}
      </WorkspacePanel>
    </div>
  );
}

function EventsTab({
  calendars,
  events,
  eventForm,
  selectedCalendarId,
  busy,
  saving,
  onCalendarChange,
  onEventChange,
  onCreate,
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(20rem,0.85fr)_minmax(0,1.35fr)]">
      <WorkspacePanel title="Create Event" description="Create a draft calendar event for the selected generated calendar.">
        <form className="space-y-4" onSubmit={onCreate}>
          <SelectControl
            label="Calendar"
            value={selectedCalendarId}
            onChange={onCalendarChange}
            options={calendars.map((calendar) => ({ value: calendar.id, label: calendarLabel(calendar) }))}
          />
          <Input label="Title" value={eventForm.title} onChange={(event) => onEventChange((current) => ({ ...current, title: event.target.value }))} />
          <SelectControl label="Audience" value={eventForm.audience} onChange={(value) => onEventChange((current) => ({ ...current, audience: value }))} options={["all", "tenant_admins", "teachers", "parents", "students"].map((value) => ({ value, label: value.replaceAll("_", " ") }))} />
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Starts" type="datetime-local" value={eventForm.starts_at} onChange={(event) => onEventChange((current) => ({ ...current, starts_at: event.target.value }))} />
            <Input label="Ends" type="datetime-local" value={eventForm.ends_at} onChange={(event) => onEventChange((current) => ({ ...current, ends_at: event.target.value }))} />
          </div>
          <Button type="submit" disabled={busy || !selectedCalendarId || !eventForm.title}>
            {saving === "event" ? "Adding..." : "Add Event"}
          </Button>
        </form>
      </WorkspacePanel>

      <WorkspacePanel title="Event List" description="Review events in the currently selected calendar range.">
        <div className="grid gap-3 lg:grid-cols-2">
          {events.length ? events.map((event) => <CalendarEventCard key={event.id} event={event} compact />) : <p className="text-sm text-text-muted">No events in this range.</p>}
        </div>
      </WorkspacePanel>
    </div>
  );
}

function ClosuresTab({
  calendars,
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
          options={calendars.map((calendar) => ({ value: calendar.id, label: calendarLabel(calendar) }))}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <Input label="Start date" type="date" value={closureForm.start_date} onChange={(event) => onClosureChange((current) => ({ ...current, start_date: event.target.value }))} />
          <Input label="End date" type="date" value={closureForm.end_date} onChange={(event) => onClosureChange((current) => ({ ...current, end_date: event.target.value }))} />
        </div>
        <Input label="Reason" value={closureForm.reason} onChange={(event) => onClosureChange((current) => ({ ...current, reason: event.target.value }))} />
        <div className="rounded-2xl border border-warning/40 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-950">
          School will be marked closed, student activities disabled, and attendance will not be expected for the selected dates.
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

function CalendarMonthView({ days }) {
  if (!days.length) {
    return <EmptyState icon={CalendarDays} title="No days in range" />;
  }
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
      {days.map((day) => (
        <div key={day.id} className="min-h-28 rounded-2xl border border-border/70 bg-surface px-3 py-3">
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-semibold text-text">{formatCalendarDate(day.calendar_date)}</p>
            <CalendarStatusBadge status={day.school_open ? "active" : "closed"}>
              {day.school_open ? "Open" : "Closed"}
            </CalendarStatusBadge>
          </div>
          <p className="mt-3 text-xs font-semibold text-text-soft">{dayTypeLabel(day.day_type)}</p>
          {day.title ? <p className="mt-1 line-clamp-2 text-xs text-text-muted">{day.title}</p> : null}
        </div>
      ))}
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
