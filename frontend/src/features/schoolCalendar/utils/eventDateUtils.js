const DAY_MS = 24 * 60 * 60 * 1000;

export const isoDate = (value) => String(value || "").slice(0, 10);

export const addIsoDays = (value, amount) => {
  const date = new Date(`${isoDate(value)}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return "";
  date.setUTCDate(date.getUTCDate() + amount);
  return date.toISOString().slice(0, 10);
};

export const inclusiveEventDateRange = (event) => {
  const start = isoDate(event?.starts_at);
  const rawEnd = isoDate(event?.ends_at);
  if (!start || !rawEnd) return null;

  const endsAtMidnight = /T00:00(?::00(?:\.000)?)?(?:Z|[+-]\d{2}:?\d{2})?$/.test(
    String(event?.ends_at || ""),
  );
  const end = event?.is_all_day && endsAtMidnight ? addIsoDays(rawEnd, -1) : rawEnd;
  return end < start ? null : { start, end };
};

export const eventOccursOnDate = (event, value) => {
  const date = isoDate(value);
  const range = inclusiveEventDateRange(event);
  return Boolean(date && range && range.start <= date && date <= range.end);
};

export const eventsForCalendarDate = (events, value) =>
  (Array.isArray(events) ? events : []).filter((event) => eventOccursOnDate(event, value));

export const inclusiveDayCount = (startValue, endValue) => {
  const start = new Date(`${isoDate(startValue)}T00:00:00Z`);
  const end = new Date(`${isoDate(endValue)}T00:00:00Z`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return 0;
  return Math.floor((end.getTime() - start.getTime()) / DAY_MS) + 1;
};

export const buildAllDayInterval = ({ eventDate, spansMultipleDays, endDate }) => {
  const start = isoDate(eventDate);
  const inclusiveEnd = spansMultipleDays ? isoDate(endDate) : start;
  if (!start || !inclusiveEnd || inclusiveEnd < start) return null;

  return {
    starts_at: new Date(`${start}T00:00:00`).toISOString(),
    ends_at: new Date(`${addIsoDays(inclusiveEnd, 1)}T00:00:00`).toISOString(),
    inclusive_start_date: start,
    inclusive_end_date: inclusiveEnd,
  };
};
