import { formatCalendarDate } from "./calendarDisplay.js";
import { inclusiveEventDateRange, isoDate } from "./eventDateUtils.js";

export const eventDateRangeLabel = (event) => {
  const range = inclusiveEventDateRange(event);
  if (!range) return formatCalendarDate(event?.starts_at, { year: "numeric" });

  const startLabel = formatCalendarDate(range.start, { year: "numeric" });
  if (range.start === range.end) return startLabel;

  const endLabel = formatCalendarDate(range.end, { year: "numeric" });
  return `${startLabel} – ${endLabel}`;
};

export const eventOccurrenceLabel = (event, occurrenceDate) => {
  const range = inclusiveEventDateRange(event);
  const occurrence = isoDate(occurrenceDate);

  if (
    !range ||
    !occurrence ||
    range.start === range.end ||
    occurrence < range.start ||
    occurrence > range.end
  ) {
    return "";
  }

  return `Showing on ${formatCalendarDate(occurrence, { year: "numeric" })}`;
};
