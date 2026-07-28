import { useCallback, useEffect, useState } from "react";
import { CalendarClock, CalendarDays, RefreshCw } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import CalendarEventCard from "../../features/schoolCalendar/components/CalendarEventCard";
import CalendarStatusBadge from "../../features/schoolCalendar/components/CalendarStatusBadge";
import { schoolCalendarService } from "../../features/schoolCalendar/api/schoolCalendarService";
import {
  dayTypeLabel,
  formatCalendarDate,
} from "../../features/schoolCalendar/utils/calendarDisplay";
import { authSession, getErrorMessage, isAbortError } from "../../services/api";

const asItems = (response) => (Array.isArray(response?.items) ? response.items : []);
const todayIso = () => new Date().toISOString().slice(0, 10);
const addDays = (isoDate, days) => {
  const date = new Date(`${isoDate}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
};
const weekdayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const dayNumber = (value) => {
  if (!value) return "-";
  const date = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("en", { day: "numeric" }).format(date);
};
const monthLabel = (start, end) => {
  const startLabel = formatCalendarDate(start, { year: "numeric" });
  const endLabel = formatCalendarDate(end, { year: "numeric" });
  return startLabel === endLabel ? startLabel : `${startLabel} - ${endLabel}`;
};

const titles = {
  admin: {
    title: "School Calendar",
    description: "View the generated school calendar, open days, closures, and published events.",
  },
  teacher: {
    title: "School Calendar",
    description: "Check open days, closures, exams, meetings, and school events.",
  },
  parent: {
    title: "Family Calendar",
    description: "Follow school days, holidays, closures, meetings, and student-facing events.",
  },
  student: {
    title: "Student Calendar",
    description: "See school days, holidays, closures, exams, and student events.",
  },
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

  const loadCalendar = useCallback(async ({ signal, quiet = false, startDate = rangeStart, endDate = rangeEnd } = {}) => {
    if (quiet) setRefreshing(true);
    else setLoading(true);
    setError("");
    try {
      const [rangeResponse, eventResponse] = await Promise.all([
        schoolCalendarService.getRange(
          { start_date: startDate, end_date: endDate },
          { signal },
        ),
        schoolCalendarService.getEvents(
          { start_date: startDate, end_date: endDate },
          { signal },
        ),
      ]);
      setDays(asItems(rangeResponse));
      setEvents(asItems(eventResponse));
    } catch (err) {
      if (!isAbortError(err)) {
        setError(getErrorMessage(err, "Failed to load school calendar."));
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [rangeEnd, rangeStart]);

  const showTodayRange = () => {
    const today = todayIso();
    const endDate = addDays(today, 34);
    setRangeStart(today);
    setRangeEnd(endDate);
    loadCalendar({ quiet: true, startDate: today, endDate });
  };

  useEffect(() => {
    const controller = new AbortController();
    loadCalendar({ signal: controller.signal });
    return () => controller.abort();
  }, [calendarScope, loadCalendar]);

  return (
    <DashboardLayout
      role={role}
      title={copy.title}
      description={copy.description}
    >
      <section className="space-y-4">
        <Card className="p-3 sm:p-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
                <CalendarClock className="h-4 w-4" />
                Viewing Range
              </div>
              <h2 className="mt-1 text-lg font-semibold text-text">
                {monthLabel(rangeStart, rangeEnd)}
              </h2>
            </div>

            <div className="grid gap-3 sm:grid-cols-[minmax(10rem,1fr)_minmax(10rem,1fr)_auto] xl:min-w-[34rem]">
              <Input
                label="Start"
                type="date"
                value={rangeStart}
                onChange={(event) => setRangeStart(event.target.value)}
              />
              <Input
                label="End"
                type="date"
                value={rangeEnd}
                onChange={(event) => setRangeEnd(event.target.value)}
              />
              <div className="flex items-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="w-full sm:w-auto"
                  onClick={showTodayRange}
                >
                  Today
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="w-full sm:w-auto"
                  onClick={() => loadCalendar({ quiet: true })}
                  disabled={refreshing}
                >
                  <RefreshCw className="h-4 w-4" />
                  Refresh
                </Button>
              </div>
            </div>
          </div>
        </Card>

        {error ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-amber-900">
            {error}
          </div>
        ) : null}

        <Card className="overflow-hidden p-0">
          <div className="flex flex-col gap-1 border-b border-border/70 px-4 py-4 sm:flex-row sm:items-end sm:justify-between sm:px-5">
            <div>
              <h3 className="section-title">Calendar</h3>
              <p className="mt-1 text-sm text-text-muted">
                Open days, closures, holidays, exams, and events in the selected range.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-sm font-semibold text-text-soft">
              <span>{days.length} days</span>
              <span>/</span>
              <span>{events.length} events</span>
            </div>
          </div>

          <div className="hidden grid-cols-7 border-b border-border/70 bg-surface-muted/40 text-center text-xs font-semibold uppercase tracking-wide text-text-muted md:grid">
            {weekdayLabels.map((label) => (
              <div key={label} className="px-3 py-2">
                {label}
              </div>
            ))}
          </div>

          <div className="p-3 sm:p-4">
            {loading ? (
              <LoadingState label="Loading calendar days..." />
            ) : days.length ? (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 md:grid-cols-7">
                {days.map((day) => (
                  <CalendarDayTile
                    key={day.id || day.date || day.calendar_date}
                    day={day}
                    eventCount={eventsForDay(events, day.calendar_date || day.date).length}
                  />
                ))}
              </div>
            ) : (
              <EmptyState icon={CalendarDays} title="No calendar days found" />
            )}
          </div>
        </Card>

        <Card className="p-4 sm:p-5">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h3 className="section-title">Published Events</h3>
              <p className="mt-1 text-sm text-text-muted">
                Events visible to your role in the selected date range.
              </p>
            </div>
            <p className="text-sm font-semibold text-text-soft">{events.length} events</p>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
            {events.length ? (
              events.map((event) => (
                <CalendarEventCard key={event.id} event={event} compact />
              ))
            ) : (
              <p className="text-sm text-text-muted">No published events in this range.</p>
            )}
          </div>
        </Card>
      </section>
    </DashboardLayout>
  );
}

function eventsForDay(events, value) {
  const isoDate = String(value || "").slice(0, 10);
  if (!isoDate) return [];
  return events.filter((event) => String(event.starts_at || "").slice(0, 10) === isoDate);
}

function CalendarDayTile({ day, eventCount = 0 }) {
  const date = day.calendar_date || day.date;
  const schoolOpen = Boolean(day.school_open);

  return (
    <div className="min-h-32 rounded-xl border border-border/70 bg-surface px-3 py-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-2xl font-semibold leading-none text-text">{dayNumber(date)}</p>
          <p className="mt-1 text-xs font-medium text-text-muted">
            {formatCalendarDate(date)}
          </p>
        </div>
        <CalendarStatusBadge status={schoolOpen ? "active" : "closed"}>
          {schoolOpen ? "Open" : "Closed"}
        </CalendarStatusBadge>
      </div>
      <p className="mt-3 text-xs font-semibold text-text-soft">
        {dayTypeLabel(day.day_type)}
      </p>
      {day.title ? (
        <p className="mt-1 line-clamp-2 text-xs text-text-muted">{day.title}</p>
      ) : null}
      {eventCount ? (
        <p className="mt-3 inline-flex rounded-full bg-primary-soft px-2.5 py-1 text-xs font-semibold text-primary">
          {eventCount} event{eventCount === 1 ? "" : "s"}
        </p>
      ) : null}
    </div>
  );
}

export default SchoolCalendarPage;
