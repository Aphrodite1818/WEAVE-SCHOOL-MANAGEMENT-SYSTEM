import { CalendarClock } from "lucide-react";

import Card from "../../../components/ui/Card";
import { audienceLabels, eventTypeLabels } from "../utils/calendarDisplay";
import {
  eventDateRangeLabel,
  eventOccurrenceLabel,
} from "../utils/eventDisplay";
import CalendarStatusBadge from "./CalendarStatusBadge";

function CalendarEventCard({ event, compact = false, occurrenceDate = "" }) {
  if (!event) return null;

  const occurrenceLabel = eventOccurrenceLabel(event, occurrenceDate);

  return (
    <Card className={compact ? "p-3" : "p-4"}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold text-text">{event.title}</p>
          <p className="mt-1 text-xs text-text-muted">
            {eventDateRangeLabel(event)}
            {event.is_all_day ? " / All day" : ""}
          </p>
          {occurrenceLabel ? (
            <p className="mt-1 text-xs font-semibold text-primary">{occurrenceLabel}</p>
          ) : null}
        </div>
        {event.status ? <CalendarStatusBadge status={event.status} /> : null}
      </div>
      {!compact && event.description ? (
        <p className="mt-3 line-clamp-3 text-sm leading-6 text-text-muted">{event.description}</p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-text-soft">
        <span className="inline-flex items-center gap-1 rounded-full bg-surface-muted/60 px-2.5 py-1">
          <CalendarClock className="h-3.5 w-3.5" />
          {eventTypeLabels[event.event_type] || "Event"}
        </span>
        <span className="rounded-full bg-surface-muted/60 px-2.5 py-1">
          {audienceLabels[event.audience] || "Visible"}
        </span>
      </div>
    </Card>
  );
}

export default CalendarEventCard;
