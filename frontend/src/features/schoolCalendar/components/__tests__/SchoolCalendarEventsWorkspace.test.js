import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const source = fs.readFileSync(
  path.resolve(process.cwd(), "src/features/schoolCalendar/components/SchoolCalendarEventsWorkspace.jsx"),
  "utf8",
);

describe("SchoolCalendarEventsWorkspace", () => {
  it("uses date-only inputs for all-day events", () => {
    expect(source).toContain('label="End date (inclusive)"');
    expect(source).toContain("allDayStartIso");
    expect(source).toContain("allDayEndIso");
  });

  it("warns without reopening closed days", () => {
    expect(source).toContain("This event overlaps");
    expect(source).toContain("will not reopen school");
    expect(source).toContain("Create Event Only");
  });
});
