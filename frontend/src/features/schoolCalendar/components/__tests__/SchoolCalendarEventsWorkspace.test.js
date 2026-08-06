import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const source = fs.readFileSync(
  path.resolve(process.cwd(), "src/features/schoolCalendar/components/SchoolCalendarEventsWorkspace.jsx"),
  "utf8",
);

describe("SchoolCalendarEventsWorkspace", () => {
  it("uses an explicit event timing selector instead of an all-day checkbox", () => {
    expect(source).toContain('label="Event timing"');
    expect(source).toContain("Specific-time event — exact start and end times");
    expect(source).toContain("Full-day event — occupies the whole selected day");
    expect(source).not.toContain('label="All-day event"');
  });

  it("clearly separates one-day and multi-day full-day events", () => {
    expect(source).toContain('label="Full-day duration"');
    expect(source).toContain("One full day");
    expect(source).toContain("Several full days");
    expect(source).toContain('label="Event date"');
    expect(source).toContain('label="Starts on"');
    expect(source).toContain('label="Ends on (inclusive)"');
  });

  it("uses exact datetime labels for specific-time events", () => {
    expect(source).toContain('label="Starts at"');
    expect(source).toContain('label="Ends at"');
    expect(source).toContain("including overnight events");
  });

  it("preserves the closed-day warning without reopening operational days", () => {
    expect(source).toContain("This event overlaps");
    expect(source).toContain("will not reopen school");
    expect(source).toContain("Create Event Only");
  });
});
