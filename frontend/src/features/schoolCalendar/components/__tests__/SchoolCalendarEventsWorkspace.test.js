import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import test from "node:test";

const source = fs.readFileSync(
  path.resolve(process.cwd(), "src/features/schoolCalendar/components/SchoolCalendarEventsWorkspace.jsx"),
  "utf8",
);

test("uses an explicit event timing selector instead of an all-day checkbox", () => {
  assert.match(source, /label="Event timing"/);
  assert.match(source, /Specific-time event — exact start and end times/);
  assert.match(source, /Full-day event — occupies the whole selected day/);
  assert.doesNotMatch(source, /label="All-day event"/);
});

test("clearly separates one-day and multi-day full-day events", () => {
  assert.match(source, /label="Full-day duration"/);
  assert.match(source, /One full day/);
  assert.match(source, /Several full days/);
  assert.match(source, /label="Event date"/);
  assert.match(source, /label="Starts on"/);
  assert.match(source, /label="Ends on \(inclusive\)"/);
});

test("uses exact datetime labels for specific-time events", () => {
  assert.match(source, /label="Starts at"/);
  assert.match(source, /label="Ends at"/);
  assert.match(source, /including overnight events/);
});

test("preserves the closed-day warning without reopening operational days", () => {
  assert.match(source, /This event overlaps/);
  assert.match(source, /will not reopen school/);
  assert.match(source, /Create Event Only/);
});
