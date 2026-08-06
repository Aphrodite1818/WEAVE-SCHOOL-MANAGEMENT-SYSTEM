import test from "node:test";
import assert from "node:assert/strict";

import {
  buildAllDayInterval,
  eventOccursOnDate,
  eventsForCalendarDate,
  inclusiveDayCount,
} from "./eventDateUtils.js";

test("single-day all-day event resolves to one visible calendar date", () => {
  const interval = buildAllDayInterval({ eventDate: "2026-08-06", spansMultipleDays: false, endDate: "" });
  assert.equal(interval.inclusive_start_date, "2026-08-06");
  assert.equal(interval.inclusive_end_date, "2026-08-06");
  assert.equal(eventOccursOnDate({ ...interval, is_all_day: true }, "2026-08-06"), true);
  assert.equal(eventOccursOnDate({ ...interval, is_all_day: true }, "2026-08-07"), false);
});

test("multi-day event appears on every affected date", () => {
  const event = {
    id: "camp",
    is_all_day: true,
    starts_at: "2026-08-06T00:00:00.000Z",
    ends_at: "2026-08-09T00:00:00.000Z",
  };
  assert.equal(eventOccursOnDate(event, "2026-08-06"), true);
  assert.equal(eventOccursOnDate(event, "2026-08-07"), true);
  assert.equal(eventOccursOnDate(event, "2026-08-08"), true);
  assert.equal(eventOccursOnDate(event, "2026-08-09"), false);
  assert.equal(eventsForCalendarDate([event], "2026-08-07").length, 1);
  assert.equal(inclusiveDayCount("2026-08-06", "2026-08-08"), 3);
});

test("timed cross-day event appears on both calendar dates", () => {
  const event = {
    is_all_day: false,
    starts_at: "2026-08-06T22:00:00.000Z",
    ends_at: "2026-08-07T02:00:00.000Z",
  };
  assert.equal(eventOccursOnDate(event, "2026-08-06"), true);
  assert.equal(eventOccursOnDate(event, "2026-08-07"), true);
  assert.equal(eventOccursOnDate(event, "2026-08-08"), false);
});
