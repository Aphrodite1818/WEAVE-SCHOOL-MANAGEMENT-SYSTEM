import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const source = fs.readFileSync(
  path.resolve(process.cwd(), "src/features/schoolCalendar/components/DayEditorStateBridge.jsx"),
  "utf8",
);

describe("DayEditorStateBridge", () => {
  it("normalizes every closed calendar day type", () => {
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

  it("clears operating hours and disables incompatible flags", () => {
    expect(source).toContain('setNativeValue(opensAt, "")');
    expect(source).toContain('setNativeValue(closesAt, "")');
    expect(source).toContain('setCheckbox(form, "School open", false)');
    expect(source).toContain('setCheckbox(form, "Student activity allowed", false)');
    expect(source).toContain('setCheckbox(form, "Student operational expectation", false)');
    expect(source).toContain('setCheckbox(form, "Workforce operational expectation", false)');
  });

  it("runs after React rerenders, select changes, and preset clicks", () => {
    expect(source).toContain("new MutationObserver(normalize)");
    expect(source).toContain('document.addEventListener("change", handleChange, true)');
    expect(source).toContain('document.addEventListener("click", handleClick, true)');
    expect(source).toContain("requestAnimationFrame");
  });

  it("shows a closed-day operating-hours explanation", () => {
    expect(source).toContain("Operating hours not applicable");
    expect(source).toContain("opening and closing times will be saved as empty");
  });
});
