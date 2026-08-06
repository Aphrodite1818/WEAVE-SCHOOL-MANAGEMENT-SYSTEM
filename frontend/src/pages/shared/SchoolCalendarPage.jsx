import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarClock, CalendarDays, RefreshCw } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import Modal from "../../components/ui/Modal";
import CalendarEventCard from "../../features/schoolCalendar/components/CalendarEventCard";
import CalendarStatusBadge from "../../features/schoolCalendar/components/CalendarStatusBadge";
import { schoolCalendarService } from "../../features/schoolCalendar/api/schoolCalendarService";
import { eventsForCalendarDate } from "../../features/schoolCalendar/utils/eventDateUtils";
import {
  dayTypeLabel,
  formatCalendarDate,
} from "../../features/schoolCalendar/utils/calendarDisplay";
import { authSession, getErrorMessage, isAbortError } from "../../services/api";

const asItems = (response) => (Array.isArray(response?.items) ? response.items : []);
const todayIso = () => new Date().toISOString().slice(0, 10);
const addDays = (value, amount) => {
  const date = new Date(`${value}T00:00:00`);
  date.setDate(date.getDate() + amount);
  return date.toISOString().slice(0, 10);
};
const weekdayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const mondayGridOffset = (value) => {
  const date = new Date(`${String(value || "").slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime()) ? 0 : (date.getDay() + 6) % 7;
};
const dayNumber = (value) => {
  const date = new Date(`${String(value || "").slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime()) ? "-" : new Intl.DateTimeFormat("en", { day: "numeric" }).format(date);
};
const monthLabel = (start, end) => {
  const startLabel = formatCalendarDate(start, { year: "numeric" });
  const endLabel = formatCalendarDate(end, { year: "numeric" });
  return startLabel === endLabel ? startLabel : `${startLabel} - ${endLabel}`;
};

const titles = {
  admin: { title: "School Calendar", description: "View the generated school calendar, open days, closures, and published events." },
  teacher: { title: "School Calendar", description: "Check open days, closures, exams, meetings, and school events." },
  parent: { title: "Family Calendar", description: "Follow school days, holidays, closures, meetings, and student-facing events." },
  student: { title: "Student Calendar", description: "See school days, holidays, closures, exams, and student events." },
};

function SchoolCalendarPage({ role = "student" }) {
  const [rangeStart, setRangeStart] = useState(todayIso());
  const [rangeEnd, setRangeEnd] = useState(addDays(todayIso(), 34));
  const [days, setDays] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const copy = titles[role] || titles.student;
  const user = authSession.getUser() || {};
  const calendarScope = `${role}:${user?.tenant_id || "global"}:${user?.membership_id || ""}:${user?.id || user?.email || ""}`;

  const orderedDays = useMemo(
    () => [...days].sort((a, b) => String(a.calendar_date || a.date).localeCompare(String(b.calendar_date || b.date))),
    [days],
  );
  const leadingBlankDays = useMemo(
    () => mondayGridOffset(orderedDays[0]?.calendar_date || orderedDays[0]?.date),
    [orderedDays],
  );

  const loadCalendar = useCallback(async ({ signal, quiet = false } = {}) => {
    quiet ? setRefreshing(true) : setLoading(true);
    setError("");
    try {
      const [rangeResponse, eventResponse] = await Promise.all([
        schoolCalendarService.getRange({ start_date: rangeStart, end_date: rangeEnd }, { signal }),
        schoolCalendarService.getEvents({ start_date: rangeStart, end_date: rangeEnd }, { signal }),
      ]);
      setDays(asItems(rangeResponse));
      setEvents(asItems(eventResponse));
    } catch (err) {
      if (!isAbortError(err)) setError(getErrorMessage(err, "Failed to load school calendar."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [rangeEnd, rangeStart]);

  useEffect(() => {
    const controller = new AbortController();
    loadCalendar({ signal: controller.signal });
    return () => controller.abort();
  }, [calendarScope, loadCalendar]);

  const showTodayRange = () => {
    setRangeStart(todayIso());
    setRangeEnd(addDays(todayIso(), 34));
  };

  return (
    <DashboardLayout role={role} title={copy.title} description={copy.description}>
      <section className="space-y-4">
        <Card className="p-3 sm:p-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
                <CalendarClock className="h-4 w-4" /> Viewing Range
              </div>
              <h2 className="mt-1 text-lg font-semibold text-text">{monthLabel(rangeStart, rangeEnd)}</h2>
            </div>
            <div className="grid gap-3 sm:grid-cols-[minmax(10rem,1fr)_minmax(10rem,1fr)_auto] xl:min-w-[34rem]">
              <Input label="Start" type="date" value={rangeStart} onChange={(event) => setRangeStart(event.target.value)} />
              <Input label="End" type="date" value={rangeEnd} onChange={(event) => setRangeEnd(event.target.value)} />
              <div className="flex items-end gap-2">
                <Button type="button" variant="outline" onClick={showTodayRange}>Today</Button>
                <Button type="button" variant="outline" className="manual-refresh-action" onClick={() => loadCalendar({ quiet: true })} disabled={refreshing}>
                  <RefreshCw className="h-4 w-4" /> Refresh
                </Button>
              </div>
            </div>
          </div>
        </Card>

        {error ? <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-900">{error}</div> : null}

        <Card className="overflow-hidden p-0">
          <div className="flex flex-col gap-1 border-b border-border/70 px-4 py-4 sm:flex-row sm:items-end sm:justify-between sm:px-5">
            <div>
              <h3 className="section-title">Calendar</h3>
              <p className="mt-1 text-sm text-text-muted">Multi-day events appear on every date they affect.</p>
            </div>
            <div className="flex gap-2 text-sm font-semibold text-text-soft"><span>{days.length} days</span><span>/</span><span>{events.length} events</span></div>
          </div>
          <div className="hidden grid-cols-7 border-b border-border/70 bg-surface-muted/40 text-center text-xs font-semibold uppercase tracking-wide text-text-muted md:grid">
            {weekdayLabels.map((label) => <div key={label} className="px-3 py-2">{label}</div>)}
          </div>
          <div className="p-3 sm:p-4">
            {loading ? <LoadingState label="Loading calendar days..." /> : orderedDays.length ? (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 md:grid-cols-7">
                {Array.from({ length: leadingBlankDays }).map((_, index) => <div key={`blank-${index}`} aria-hidden="true" className="hidden min-h-32 md:block" />)}
                {orderedDays.map((day) => {
                  const date = day.calendar_date || day.date;
                  return <CalendarDayTile key={day.id || date} day={day} dayEvents={eventsForCalendarDate(events, date)} />;
                })}
              </div>
            ) : <EmptyState icon={CalendarDays} title="No calendar days found" />}
          </div>
        </Card>

        <Card className="p-4 sm:p-5">
          <div className="flex items-end justify-between">
            <div><h3 className="section-title">Published Events</h3><p className="mt-1 text-sm text-text-muted">Events visible to your role in the selected range.</p></div>
            <p className="text-sm font-semibold text-text-soft">{events.length} events</p>
          </div>
          <div className="mt-4 grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
            {events.length ? events.map((event) => <CalendarEventCard key={event.id} event={event} compact />) : <p className="text-sm text-text-muted">No published events in this range.</p>}
          </div>
        </Card>
      </section>
    </DashboardLayout>
  );
}

function CalendarDayTile({ day, dayEvents = [] }) {
  const [modalOpen, setModalOpen] = useState(false);
  const date = day.calendar_date || day.date;
  const schoolOpen = Boolean(day.school_open);
  return (
    <>
      <button type="button" className="min-h-32 rounded-xl border border-border/70 bg-surface px-3 py-3 text-left transition-colors hover:border-primary/50" onClick={() => setModalOpen(true)}>
        <div className="flex items-start justify-between gap-2">
          <div><p className="text-2xl font-semibold leading-none text-text">{dayNumber(date)}</p><p className="mt-1 text-xs font-medium text-text-muted">{formatCalendarDate(date)}</p></div>
          <CalendarStatusBadge status={schoolOpen ? "active" : "closed"}>{schoolOpen ? "Open" : "Closed"}</CalendarStatusBadge>
        </div>
        <p className="mt-3 text-xs font-semibold text-text-soft">{dayTypeLabel(day.day_type)}</p>
        {day.title ? <p className="mt-1 line-clamp-2 text-xs text-text-muted">{day.title}</p> : null}
        {dayEvents.length ? <p className="mt-3 inline-flex rounded-full bg-primary-soft px-2.5 py-1 text-xs font-semibold text-primary">{dayEvents.length} event{dayEvents.length === 1 ? "" : "s"}</p> : null}
      </button>
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={formatCalendarDate(date)} placement="center">
        <div className="space-y-4">
          <div className="flex items-center justify-between"><span className="text-lg font-semibold text-text">{dayTypeLabel(day.day_type)}</span><CalendarStatusBadge status={schoolOpen ? "active" : "closed"}>{schoolOpen ? "Open" : "Closed"}</CalendarStatusBadge></div>
          {day.title ? <p className="text-sm text-text-muted">{day.title}</p> : null}
          {dayEvents.length ? <div className="space-y-3 pt-2"><h4 className="text-xs font-bold uppercase tracking-wide text-text-muted">Events</h4>{dayEvents.map((event) => <CalendarEventCard key={event.id} event={event} compact />)}</div> : <p className="text-sm text-text-muted">No events on this date.</p>}
          <div className="flex justify-end pt-2"><Button type="button" onClick={() => setModalOpen(false)}>Close</Button></div>
        </div>
      </Modal>
    </>
  );
}

export default SchoolCalendarPage;
