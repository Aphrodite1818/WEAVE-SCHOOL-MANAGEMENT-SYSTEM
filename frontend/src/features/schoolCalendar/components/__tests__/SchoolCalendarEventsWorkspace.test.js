import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import test from "node:test";

const source = fs.readFileSync(
  path.resolve(
    process.cwd(),
    "src/features/schoolCalendar/components/SchoolCalendarEventsWorkspace.jsx",
  ),
  "utf8",
);

test("uses an explicit event timing selector instead of an all-day checkbox", () => {
  assert.match(source, /label="Event timing"/);
  assert.match(source, /Specific start and end time/);
  assert.match(source, /Full-day event/);
  assert.doesNotMatch(source, /label="All-day event"/);
});

test("clearly separates one-day and multi-day full-day events", () => {
  assert.match(source, /label="Duration"/);
  assert.match(source, /One full day/);
  assert.match(source, /Several full days/);
  assert.match(source, /label="Event date"/);
  assert.match(source, /label="Starts on"/);
  assert.match(source, /label="Ends on \(inclusive\)"/);
});

test("uses exact datetime labels for specific-time events", () => {
  assert.match(source, /label="Starts at"/);
  assert.match(source, /label="Ends at"/);
  assert.match(source, /type="datetime-local"/);
});

test("preserves the closed-day warning without reopening operational days", () => {
  assert.match(source, /Overlaps \{closedDays\.length\} closed calendar day/);
  assert.match(
    source,
    /Saving this event will not reopen school or change\s+attendance rules[.]/,
  );
});

test("calendar validation errors use field-friendly minimum length language", () => {
  assert.match(source, /getCalendarErrorMessage/);
  assert.match(source, /Failed to save calendar event/);
  assert.match(source, /Failed to cancel event/);
});
