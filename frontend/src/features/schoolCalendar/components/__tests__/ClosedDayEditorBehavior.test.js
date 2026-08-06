import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const source = fs.readFileSync(
  path.resolve(process.cwd(), "src/features/schoolCalendar/components/ClosedDayEditorBehavior.jsx"),
  "utf8",
);

describe("ClosedDayEditorBehavior", () => {
  it("prevents creating emergency closures from the day editor", () => {
    expect(source).toContain('item.value === "emergency_closure"');
    expect(source).toContain("option.remove()");
  });

  it("preserves existing emergency closure days as read-only workflow values", () => {
    expect(source).toContain('dayType.value === "emergency_closure"');
    expect(source).toContain("option.disabled = true");
    expect(source).toContain("managed in Closures");
  });

  it("explains that closures use the dedicated audited workflow", () => {
    expect(source).toContain("Emergency closures are managed from the Closures page");
    expect(source).toContain("one date or an entire date range");
  });
});
