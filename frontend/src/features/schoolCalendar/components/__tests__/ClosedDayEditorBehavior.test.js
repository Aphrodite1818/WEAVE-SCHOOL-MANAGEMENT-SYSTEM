import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const source = fs.readFileSync(
  path.resolve(
    process.cwd(),
    "src/features/schoolCalendar/components/ClosedDayEditorBehavior.jsx",
  ),
  "utf8",
);

describe("ClosedDayEditorBehavior", () => {
  it("reads the custom SearchableSelect combobox instead of requiring a native select", () => {
    expect(source).toContain("dayTypeCombobox");
    expect(source).toContain("[role=\"combobox\"]");
    expect(source).toContain("DAY_TYPE_BY_LABEL");
    expect(source).not.toContain("dayType instanceof HTMLSelectElement");
  });

  it("maps every closed day label to its backend day type", () => {
    for (const [label, dayType] of [
      ["weekend", "weekend"],
      ["public holiday", "public_holiday"],
      ["school holiday", "school_holiday"],
      ["mid term break", "mid_term_break"],
      ["emergency closure", "emergency_closure"],
    ]) {
      expect(source).toContain(`["${label}", "${dayType}"]`);
    }
  });

  it("locates the actual calendar-day form by its Save Day action", () => {
    expect(source).toContain('button[type="submit"]');
    expect(source).toContain('=== "save day"');
  });

  it("clears operating hours and every incompatible operational flag", () => {
    expect(source).toContain('setControlledValue(opensAt, "")');
    expect(source).toContain('setControlledValue(closesAt, "")');
    expect(source).toContain('setCheckbox(form, "School open", false)');
    expect(source).toContain('setCheckbox(form, "Student activity allowed", false)');
    expect(source).toContain(
      'setCheckbox(form, "Student operational expectation", false)',
    );
    expect(source).toContain(
      'setCheckbox(form, "Workforce operational expectation", false)',
    );
  });

  it("hides closed-day time inputs and removes them from browser validation", () => {
    expect(source).toContain("element.disabled = !visible");
    expect(source).toContain("element.required = visible");
    expect(source).toContain("container.style.display");
    expect(source).toContain("Operating hours not applicable");
  });

  it("normalizes after combobox selection, rerender, and submission", () => {
    expect(source).toContain('addEventListener("click", handleInteraction, true)');
    expect(source).toContain('addEventListener("submit", handleSubmit, true)');
    expect(source).toContain("MutationObserver");
    expect(source).toContain("requestAnimationFrame");
    expect(source).toContain("requestSubmit()");
  });
});
