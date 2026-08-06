import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const source = fs.readFileSync(
  path.resolve(process.cwd(), "src/features/schoolCalendar/components/ClosedDayEditorBehavior.jsx"),
  "utf8",
);

describe("ClosedDayEditorBehavior", () => {
  it("treats non-operational day types as closed", () => {
    for (const dayType of [
      "weekend",
      "public_holiday",
      "school_holiday",
      "mid_term_break",
      "emergency_closure",
    ]) {
      expect(source).toContain(`"${dayType}"`);
    }
  });

  it("clears operating hours and all operational flags for closed days", () => {
    expect(source).toContain('setControlledValue(opensAt, "")');
    expect(source).toContain('setControlledValue(closesAt, "")');
    expect(source).toContain('setCheckbox(form, "School open", false)');
    expect(source).toContain('setCheckbox(form, "Student activity allowed", false)');
    expect(source).toContain('setCheckbox(form, "Student operational expectation", false)');
    expect(source).toContain('setCheckbox(form, "Workforce operational expectation", false)');
  });

  it("replaces irrelevant time fields with a clear closed-day explanation", () => {
    expect(source).toContain("Operating hours not applicable");
    expect(source).toContain("opening and closing times will be saved as empty");
    expect(source).toContain("ensureOperatingHoursNotice(form, isClosedDay)");
  });

  it("normalizes after selects, preset clicks, rerenders, and submission", () => {
    expect(source).toContain('addEventListener("change", handleChange, true)');
    expect(source).toContain('addEventListener("click", handleClick, true)');
    expect(source).toContain('addEventListener("submit", handleSubmit, true)');
    expect(source).toContain("queueMicrotask");
    expect(source).toContain("MutationObserver");
  });

  it("prevents creating emergency closures from the day editor", () => {
    expect(source).toContain('item.value === "emergency_closure"');
    expect(source).toContain("option.remove()");
  });

  it("preserves existing emergency closure days as read-only workflow values", () => {
    expect(source).toContain('dayType.value === "emergency_closure"');
    expect(source).toContain("option.disabled = true");
    expect(source).toContain("managed in Closures");
  });
});
