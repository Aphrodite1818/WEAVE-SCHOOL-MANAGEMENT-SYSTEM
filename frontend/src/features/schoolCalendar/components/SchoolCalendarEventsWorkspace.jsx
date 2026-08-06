import { useCallback, useEffect, useMemo, useState } from "react";

import EmptyState from "../../../components/shared/EmptyState";
import LoadingState from "../../../components/shared/LoadingState";
import { getErrorMessage, isAbortError } from "../../../services/api";
import { academicService } from "../../../services/academicService";
import Button from "../../../components/ui/Button";
import Input from "../../../components/ui/Input";
import Modal from "../../../components/ui/Modal";
import { SelectControl, WorkspacePanel } from "../../academic-admin/AcademicWorkspacePrimitives";
import { schoolCalendarService } from "../api/schoolCalendarService";
import {
  buildAllDayInterval,
  inclusiveDayCount,
  inclusiveEventDateRange,
} from "../utils/eventDateUtils";
import CalendarEventCard from "./CalendarEventCard";

const asItems = (response) => (Array.isArray(response?.items) ? response.items : []);
const todayIso = () => new Date().toISOString().slice(0, 10);
const titleCase = (value) => String(value || "").replaceAll("_", " ").replace(/\b\w/g, (match) => match.toUpperCase());
const formatTermName = (term) => String(term?.display_name || term?.name || "Term").replaceAll("_", " ");
const calendarLabel = (calendar, sessions, terms) => {
  const session = sessions.find((item) => item.id === calendar?.academic_session_id);
  const term = terms.find((item) => item.id === calendar?.academic_term_id);
  return `${session?.name || "Selected session"} - ${formatTermName(term)} - ${titleCase(calendar?.status || "draft")}`;
};

const defaultForm = () => ({
  title: "",
  description: "",
  event_type: "academic",
  audience: "all",
  timing_mode: "specific_time",
  full_day_duration: "one_day",
  event_date: todayIso(),
  end_date: todayIso(),
  starts_at: `${todayIso()}T08:00`,
  ends_at: `${todayIso()}T09:00`,
  location: "",
});

const localDateTimeToIso = (value) => new Date(value).toISOString();

function SchoolCalendarEventsWorkspace() {
  const [sessions, setSessions] = useState([]);
  const [terms, setTerms] = useState([]);
  const [calendars, setCalendars] = useState([]);
  const [events, setEvents] = useState([]);
  const [selectedCalendarId, setSelectedCalendarId] = useState("");
  const [eventStatus, setEventStatus] = useState("");
  const [eventAudience, setEventAudience] = useState("");
  const [form, setForm] = useState(defaultForm);
  const [editingEventId, setEditingEventId] = useState("");
  const [closedDays, setClosedDays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [cancelTarget, setCancelTarget] = useState(null);
  const [cancelReason, setCancelReason] = useState("");

  const selectedCalendar = useMemo(
    () => calendars.find((item) => item.id === selectedCalendarId) || null,
    [calendars, selectedCalendarId],
  );

  const isFullDay = form.timing_mode === "full_day";
  const spansMultipleDays = isFullDay && form.full_day_duration === "multiple_days";

  const eventRange = useMemo(() => {
    if (form.timing_mode === "full_day") {
      return {
        start: form.event_date,
        end: form.full_day_duration === "multiple_days" ? form.end_date : form.event_date,
      };
    }
    return {
      start: String(form.starts_at || "").slice(0, 10),
      end: String(form.ends_at || "").slice(0, 10),
    };
  }, [form]);

  const spanDays = inclusiveDayCount(eventRange.start, eventRange.end);

  const loadBase = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [sessionResponse, termResponse, calendarResponse] = await Promise.all([
        academicService.listSessions({ limit: 100 }),
        academicService.listTerms({ limit: 100 }),
        schoolCalendarService.listAdminCalendars({ limit: 100 }),
      ]);
      const sessionItems = asItems(sessionResponse);
      const termItems = asItems(termResponse);
      const calendarItems = asItems(calendarResponse);
      const currentTerm = termItems.find((item) => item.is_current) || termItems.find((item) => item.status !== "closed");
      const currentCalendar = calendarItems.find((item) => item.academic_term_id === currentTerm?.id) || calendarItems[0] || null;
      setSessions(sessionItems);
      setTerms(termItems);
      setCalendars(calendarItems);
      setSelectedCalendarId((current) => calendarItems.some((item) => item.id === current) ? current : currentCalendar?.id || "");
    } catch (err) {
      if (!isAbortError(err)) setError(getErrorMessage(err, "Failed to load calendar events."));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadEvents = useCallback(async () => {
    if (!selectedCalendarId) return setEvents([]);
    try {
      const response = await schoolCalendarService.getAdminEvents({
        calendar_id: selectedCalendarId,
        status: eventStatus || undefined,
        audience: eventAudience || undefined,
      });
      setEvents(asItems(response));
    } catch (err) {
      if (!isAbortError(err)) setError(getErrorMessage(err, "Failed to load events."));
    }
  }, [eventAudience, eventStatus, selectedCalendarId]);

  const inspectClosedDays = useCallback(async () => {
    if (!selectedCalendarId || !eventRange.start || !eventRange.end || eventRange.end < eventRange.start) {
      setClosedDays([]);
      return;
    }
    try {
      const response = await schoolCalendarService.getDays({
        calendar_id: selectedCalendarId,
        start_date: eventRange.start,
        end_date: eventRange.end,
      });
      setClosedDays(asItems(response).filter((day) => !day.school_open));
    } catch {
      setClosedDays([]);
    }
  }, [eventRange.end, eventRange.start, selectedCalendarId]);

  useEffect(() => { loadBase(); }, [loadBase]);
  useEffect(() => { loadEvents(); }, [loadEvents]);
  useEffect(() => { inspectClosedDays(); }, [inspectClosedDays]);

  const resetForm = () => {
    setEditingEventId("");
    setForm(defaultForm());
    setClosedDays([]);
  };

  const buildPayload = () => {
    const allDayInterval = isFullDay
      ? buildAllDayInterval({
          eventDate: form.event_date,
          spansMultipleDays,
          endDate: form.end_date,
        })
      : null;

    if (isFullDay && !allDayInterval) return null;

    return {
      title: form.title.trim(),
      description: form.description.trim() || null,
      event_type: form.event_type,
      audience: form.audience,
      is_all_day: isFullDay,
      starts_at: allDayInterval?.starts_at || localDateTimeToIso(form.starts_at),
      ends_at: allDayInterval?.ends_at || localDateTimeToIso(form.ends_at),
      location: form.location.trim() || null,
    };
  };

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!selectedCalendarId || !form.title.trim()) return;
    if (!eventRange.start || !eventRange.end || eventRange.end < eventRange.start) {
      setError("Event end must not be before its start.");
      return;
    }

    setSaving("event");
    try {
      const payload = buildPayload();
      if (!payload) throw new Error("Invalid event date range.");
      if (editingEventId) {
        await schoolCalendarService.updateEvent(editingEventId, payload);
        setMessage("Calendar event updated.");
      } else {
        await schoolCalendarService.createEvent({ ...payload, calendar_id: selectedCalendarId });
        setMessage("Calendar event created as draft.");
      }
      resetForm();
      await loadEvents();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to save calendar event."));
    } finally {
      setSaving("");
    }
  };

  const startEdit = (item) => {
    const range = inclusiveEventDateRange(item);
    const start = String(item.starts_at || "");
    const end = String(item.ends_at || "");
    const fullDay = Boolean(item.is_all_day);
    const multipleDays = Boolean(range && range.start !== range.end);

    setEditingEventId(item.id);
    setForm({
      title: item.title || "",
      description: item.description || "",
      event_type: item.event_type || "academic",
      audience: item.audience || "all",
      timing_mode: fullDay ? "full_day" : "specific_time",
      full_day_duration: multipleDays ? "multiple_days" : "one_day",
      event_date: range?.start || start.slice(0, 10),
      end_date: range?.end || end.slice(0, 10),
      starts_at: start.slice(0, 16),
      ends_at: end.slice(0, 16),
      location: item.location || "",
    });
  };

  const publish = async (id) => {
    setSaving("action");
    try {
      await schoolCalendarService.publishEvent(id);
      await loadEvents();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to publish event."));
    } finally {
      setSaving("");
    }
  };

  const cancelEvent = async () => {
    if (!cancelTarget || cancelReason.trim().length < 3) return;
    setSaving("action");
    try {
      await schoolCalendarService.cancelEvent(cancelTarget, cancelReason.trim());
      setCancelTarget(null);
      setCancelReason("");
      await loadEvents();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to cancel event."));
    } finally {
      setSaving("");
    }
  };

  if (loading) return <LoadingState label="Loading calendar events..." />;

  return (
    <section className="space-y-4">
      {error ? <Notice tone="error" message={error} /> : null}
      {message ? <Notice tone="success" message={message} /> : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(20rem,0.85fr)_minmax(0,1.35fr)]">
        <WorkspacePanel
          title={editingEventId ? "Edit Event" : "Create Event"}
          description="Choose whether the event occupies whole calendar days or runs at specific times."
        >
          <form className="space-y-4" onSubmit={submit}>
            <SelectControl label="Calendar" value={selectedCalendarId} onChange={setSelectedCalendarId} options={calendars.map((calendar) => ({ value: calendar.id, label: calendarLabel(calendar, sessions, terms) }))} />
            <Input label="Title" value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} />
            <Input label="Description" value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} />
            <SelectControl label="Event type" value={form.event_type} onChange={(value) => setForm((current) => ({ ...current, event_type: value }))} options={["academic", "holiday", "examination", "meeting", "activity", "emergency", "other"].map((value) => ({ value, label: titleCase(value) }))} />
            <SelectControl label="Audience" value={form.audience} onChange={(value) => setForm((current) => ({ ...current, audience: value }))} options={["all", "tenant_admins", "teachers", "parents", "students"].map((value) => ({ value, label: titleCase(value) }))} />

            <div className="rounded-2xl border border-border/70 bg-surface-muted/40 p-3">
              <SelectControl
                label="Event timing"
                value={form.timing_mode}
                onChange={(value) => setForm((current) => ({ ...current, timing_mode: value }))}
                options={[
                  { value: "specific_time", label: "Specific-time event — exact start and end times" },
                  { value: "full_day", label: "Full-day event — occupies the whole selected day" },
                ]}
              />
              <p className="mt-2 text-xs text-text-muted">
                {isFullDay
                  ? "Use this when clock times do not matter and the event occupies the full day."
                  : "Use this when the event begins and ends at exact times, including overnight events."}
              </p>
            </div>

            {isFullDay ? (
              <div className="space-y-3 rounded-2xl border border-border/70 bg-surface-muted/40 p-3">
                <SelectControl
                  label="Full-day duration"
                  value={form.full_day_duration}
                  onChange={(value) => setForm((current) => ({
                    ...current,
                    full_day_duration: value,
                    end_date: value === "one_day" ? current.event_date : current.end_date || current.event_date,
                  }))}
                  options={[
                    { value: "one_day", label: "One full day" },
                    { value: "multiple_days", label: "Several full days" },
                  ]}
                />

                {spansMultipleDays ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Input
                      label="Starts on"
                      type="date"
                      value={form.event_date}
                      onChange={(event) => setForm((current) => ({ ...current, event_date: event.target.value }))}
                    />
                    <Input
                      label="Ends on (inclusive)"
                      type="date"
                      min={form.event_date}
                      value={form.end_date}
                      onChange={(event) => setForm((current) => ({ ...current, end_date: event.target.value }))}
                    />
                  </div>
                ) : (
                  <Input
                    label="Event date"
                    type="date"
                    value={form.event_date}
                    onChange={(event) => setForm((current) => ({ ...current, event_date: event.target.value, end_date: event.target.value }))}
                  />
                )}
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                <Input label="Starts at" type="datetime-local" value={form.starts_at} onChange={(event) => setForm((current) => ({ ...current, starts_at: event.target.value }))} />
                <Input label="Ends at" type="datetime-local" value={form.ends_at} onChange={(event) => setForm((current) => ({ ...current, ends_at: event.target.value }))} />
              </div>
            )}

            {spanDays > 1 ? (
              <div className="rounded-2xl border border-border/70 bg-surface-muted px-4 py-3 text-sm text-text-muted">
                This event covers <strong className="text-text">{spanDays} calendar days</strong>, from {eventRange.start} through {eventRange.end}. It will appear on every affected date.
              </div>
            ) : null}

            {closedDays.length ? (
              <div className="rounded-2xl border border-warning/40 bg-warning-soft px-4 py-3 text-sm text-amber-950">
                <p className="font-semibold">This event overlaps {closedDays.length} closed calendar day{closedDays.length === 1 ? "" : "s"}.</p>
                <p className="mt-1">Creating it will not reopen school, enable attendance, or change operating hours.</p>
                <p className="mt-2 text-xs font-medium">Affected dates: {closedDays.map((day) => day.calendar_date).join(", ")}</p>
              </div>
            ) : null}

            <Input label="Location" value={form.location} onChange={(event) => setForm((current) => ({ ...current, location: event.target.value }))} />
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={Boolean(saving) || !selectedCalendar || !form.title.trim()}>
                {saving === "event" ? "Saving..." : editingEventId ? "Save Event" : closedDays.length ? "Create Event Only" : "Add Event"}
              </Button>
              {editingEventId ? <Button type="button" variant="outline" onClick={resetForm}>Cancel Edit</Button> : null}
            </div>
          </form>
        </WorkspacePanel>

        <WorkspacePanel title="Event List" description="Review events for the selected calendar.">
          <div className="mb-4 grid gap-3 sm:grid-cols-2">
            <SelectControl label="Status" value={eventStatus} onChange={setEventStatus} options={[{ value: "", label: "All statuses" }, { value: "draft", label: "Draft" }, { value: "published", label: "Published" }, { value: "cancelled", label: "Cancelled" }]} />
            <SelectControl label="Audience" value={eventAudience} onChange={setEventAudience} options={[{ value: "", label: "All audiences" }, { value: "all", label: "All" }, { value: "tenant_admins", label: "Admins" }, { value: "teachers", label: "Teachers" }, { value: "parents", label: "Parents" }, { value: "students", label: "Students" }]} />
          </div>
          {events.length ? (
            <div className="grid gap-3 lg:grid-cols-2">
              {events.map((item) => (
                <div key={item.id} className="space-y-2">
                  <CalendarEventCard event={item} compact />
                  <div className="flex flex-wrap gap-2">
                    {item.status !== "cancelled" ? <Button type="button" size="small" variant="outline" onClick={() => startEdit(item)}>Edit</Button> : null}
                    {item.status === "draft" ? <Button type="button" size="small" onClick={() => publish(item.id)}>Publish</Button> : null}
                    {item.status !== "cancelled" ? <Button type="button" size="small" variant="outline" onClick={() => setCancelTarget(item.id)}>Cancel</Button> : null}
                  </div>
                </div>
              ))}
            </div>
          ) : <EmptyState title="No events in this calendar" />}
        </WorkspacePanel>
      </div>

      <Modal open={Boolean(cancelTarget)} onClose={() => setCancelTarget(null)} title="Cancel event" placement="center">
        <div className="space-y-4">
          <Input label="Reason" value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setCancelTarget(null)}>Keep Event</Button>
            <Button type="button" variant="danger" disabled={cancelReason.trim().length < 3 || saving === "action"} onClick={cancelEvent}>Cancel Event</Button>
          </div>
        </div>
      </Modal>
    </section>
  );
}

function Notice({ tone, message }) {
  const className = tone === "success" ? "border-success/30 bg-success-soft text-success" : "border-error/30 bg-error-soft text-error";
  return <div className={`rounded-2xl border px-4 py-3 text-sm font-medium ${className}`}>{message}</div>;
}

export default SchoolCalendarEventsWorkspace;
