import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

import {
  eventDateRangeLabel,
  eventOccurrenceLabel,
} from "./eventDisplay.js";
import { eventsForCalendarDate } from "./eventDateUtils.js";

const multiDayEvent = {
  id: "camp",
  title: "School camp",
  is_all_day: true,
  starts_at: "2026-08-11T00:00:00.000Z",
  ends_at: "2026-08-16T00:00:00.000Z",
};

test("multi-day events are projected onto every inclusive calendar date", () => {
  for (const date of [
    "2026-08-11",
    "2026-08-12",
    "2026-08-13",
    "2026-08-14",
    "2026-08-15",
  ]) {
    assert.deepEqual(eventsForCalendarDate([multiDayEvent], date), [multiDayEvent]);
  }

  assert.deepEqual(eventsForCalendarDate([multiDayEvent], "2026-08-16"), []);
});

test("multi-day event labels show the complete inclusive date range", () => {
  assert.equal(
    eventDateRangeLabel(multiDayEvent),
    "Aug 11, 2026 – Aug 15, 2026",
  );
});

test("occurrence labels use the selected calendar date inside the event range", () => {
  assert.equal(
    eventOccurrenceLabel(multiDayEvent, "2026-08-13"),
    "Showing on Aug 13, 2026",
  );
  assert.equal(eventOccurrenceLabel(multiDayEvent, "2026-08-16"), "");
});

test("single-day events do not show a redundant occurrence label", () => {
  const event = {
    is_all_day: true,
    starts_at: "2026-08-11T00:00:00.000Z",
    ends_at: "2026-08-12T00:00:00.000Z",
  };

  assert.equal(eventDateRangeLabel(event), "Aug 11, 2026");
  assert.equal(eventOccurrenceLabel(event, "2026-08-11"), "");
});

test("calendar day tiles render event titles and pass occurrence context to cards", () => {
  const source = fs.readFileSync(
    path.resolve(process.cwd(), "src/pages/shared/SchoolCalendarPage.jsx"),
    "utf8",
  );

  assert.match(source, /dayEvents\.slice\(0, 2\)/);
  assert.match(source, /event\.title \|\| "Calendar event"/);
  assert.match(source, /\+\{dayEvents\.length - 2\} more/);
  assert.match(source, /occurrenceDate=\{date\}/);
});
