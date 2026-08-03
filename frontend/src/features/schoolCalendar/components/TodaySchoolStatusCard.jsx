import { CalendarDays, Clock, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

import Card from "../../../components/ui/Card";
import {
  dayTypeLabel,
  formatCalendarDate,
  formatCalendarTime,
  passiveAttendanceText,
  schoolOpenLabel,
} from "../utils/calendarDisplay";
import CalendarStatusBadge from "./CalendarStatusBadge";

function TodaySchoolStatusCard({ today, upcoming, role = "student", admin = false }) {
  const events = Array.isArray(today?.events) ? today.events : [];
  const upcomingEvents = Array.isArray(upcoming?.events) ? upcoming.events : [];
  const nextEvent = events[0] || upcomingEvents[0] || null;

  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            Today's school status
          </p>
          <h3 className="mt-1 text-lg font-semibold text-text">{schoolOpenLabel(today)}</h3>
          <p className="mt-1 text-sm text-text-muted">
            {dayTypeLabel(today?.day_type)} / {formatCalendarDate(today?.date, { year: "numeric" })}
          </p>
        </div>
        <CalendarStatusBadge status={today?.school_open ? "active" : today?.code === "ok" ? "closed" : "draft"}>
          {today?.code === "ok" ? (today.school_open ? "Open" : "Closed") : "Setup"}
        </CalendarStatusBadge>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <InfoPill
          icon={Clock}
          label="Hours"
          value={
            today?.opens_at || today?.closes_at
              ? `${formatCalendarTime(today.opens_at)} - ${formatCalendarTime(today.closes_at)}`
              : "No hours set"
          }
        />
        <InfoPill
          icon={CalendarDays}
          label="Next open day"
          value={formatCalendarDate(today?.next_operational_day, { year: "numeric" })}
        />
      </div>

      <p className="mt-4 rounded-xl bg-surface-muted/40 px-3 py-2 text-sm font-medium text-text-soft">
        {passiveAttendanceText(today, role)}
      </p>

      {nextEvent ? (
        <div className="mt-4 rounded-xl border border-border/70 px-3 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Next visible event</p>
          <p className="mt-1 text-sm font-semibold text-text">{nextEvent.title}</p>
          <p className="mt-0.5 text-xs text-text-muted">
            {formatCalendarDate(nextEvent.starts_at, { year: "numeric" })}
          </p>
        </div>
      ) : null}

      {admin ? (
        <Link
          to="/admin/academic/school-calendar"
          className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-primary hover:text-primary-hover"
        >
          Open Calendar
          <ExternalLink className="h-4 w-4" />
        </Link>
      ) : null}
    </Card>
  );
}

function InfoPill({ icon: Icon, label, value }) {
  return (
    <div className="rounded-xl border border-border/70 bg-surface px-3 py-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
        <Icon className="h-4 w-4" />
        {label}
      </div>
      <p className="mt-1 truncate text-sm font-semibold text-text">{value}</p>
    </div>
  );
}

export default TodaySchoolStatusCard;
