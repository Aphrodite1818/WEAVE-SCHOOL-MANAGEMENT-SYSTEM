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

  it("clears operating hours and every incompatible operational flag", () => {
    expect(source).toContain('setControlledValue(opensAt, "")');
    expect(source).toContain('setControlledValue(closesAt, "")');
    expect(source).toContain('setCheckbox(form, "School open", false)');
    expect(source).toContain('setCheckbox(form, "Student activity allowed", false)');
    expect(source).toContain('setCheckbox(form, "Student operational expectation", false)');
    expect(source).toContain('setCheckbox(form, "Workforce operational expectation", false)');
  });

  it("removes closed-day time inputs from browser validation", () => {
    expect(source).toContain("element.disabled = !visible");
    expect(source).toContain("element.required = visible");
    expect(source).toContain("container.style.display");
  });

  it("shows an explicit closed-day operating-hours state", () => {
    expect(source).toContain("Operating hours not applicable");
    expect(source).toContain("opening and closing times will be saved as empty");
    expect(source).toContain("ensureHoursNotice(form, closed)");
  });

  it("normalizes after all relevant form interactions and React rerenders", () => {
    expect(source).toContain('addEventListener("change", handleInteraction, true)');
    expect(source).toContain('addEventListener("input", handleInteraction, true)');
    expect(source).toContain('addEventListener("click", handleInteraction, true)');
    expect(source).toContain("queueMicrotask");
    expect(source).toContain("requestAnimationFrame");
    expect(source).toContain("MutationObserver");
  });

  it("blocks the first submit until controlled React values are synchronized", () => {
    expect(source).toContain('addEventListener("submit", handleSubmit, true)');
    expect(source).toContain("event.preventDefault()");
    expect(source).toContain("new WeakSet()");
    expect(source).toContain("requestSubmit()");
  });
});
