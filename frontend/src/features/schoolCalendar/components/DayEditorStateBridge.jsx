import { useEffect } from "react";

const CLOSED_DAY_TYPES = new Set([
  "weekend",
  "public_holiday",
  "school_holiday",
  "mid_term_break",
  "emergency_closure",
]);

const findDayEditorForm = () =>
  Array.from(document.querySelectorAll("form")).find((form) =>
    form.textContent?.includes("Calendar day"),
  );

const findControlByLabel = (form, labelText) => {
  const normalized = labelText.trim().toLowerCase();
  const labels = Array.from(form.querySelectorAll("label"));
  const label = labels.find((candidate) =>
    candidate.textContent?.trim().toLowerCase().startsWith(normalized),
  );
  if (!label) return null;

  const htmlFor = label.getAttribute("for");
  if (htmlFor) return form.querySelector(`#${CSS.escape(htmlFor)}`);

  return (
    label.querySelector("input, select, textarea") ||
    label.parentElement?.querySelector("input, select, textarea, button[role='combobox']") ||
    null
  );
};

const setNativeValue = (element, value) => {
  if (!(element instanceof HTMLInputElement || element instanceof HTMLSelectElement)) return;
  const prototype = element instanceof HTMLInputElement
    ? HTMLInputElement.prototype
    : HTMLSelectElement.prototype;
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
  descriptor?.set?.call(element, value);
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
};

const setCheckbox = (form, labelText, checked) => {
  const control = findControlByLabel(form, labelText);
  if (!(control instanceof HTMLInputElement) || control.type !== "checkbox") return;
  if (control.checked !== checked) control.click();
  control.disabled = !checked;
  control.closest("label, div")?.setAttribute("aria-disabled", String(!checked));
};

const setControlVisible = (control, visible) => {
  const wrapper = control?.closest("div");
  if (!wrapper) return;
  wrapper.hidden = !visible;
  wrapper.setAttribute("aria-hidden", String(!visible));
};

const ensureClosedNotice = (form, visible) => {
  let notice = form.querySelector("[data-closed-day-hours-notice]");
  if (!notice) {
    notice = document.createElement("div");
    notice.dataset.closedDayHoursNotice = "true";
    notice.className = "mt-4 rounded-2xl border border-border/70 bg-surface-muted/40 px-4 py-3 text-sm text-text-muted";
    notice.innerHTML = "<strong class='text-text'>Operating hours not applicable.</strong> This day is closed, so opening and closing times will be saved as empty.";
    const title = findControlByLabel(form, "Title");
    title?.closest("div")?.parentElement?.insertAdjacentElement("afterend", notice);
  }
  notice.hidden = !visible;
  notice.setAttribute("aria-hidden", String(!visible));
};

const readDayType = (form) => {
  const control = findControlByLabel(form, "Day type");
  if (control instanceof HTMLSelectElement) return control.value;
  return "";
};

const normalizeClosedDay = (form) => {
  const dayType = readDayType(form);
  if (!dayType) return;

  const closed = CLOSED_DAY_TYPES.has(dayType);
  const opensAt = findControlByLabel(form, "Opens at");
  const closesAt = findControlByLabel(form, "Closes at");

  setControlVisible(opensAt, !closed);
  setControlVisible(closesAt, !closed);
  ensureClosedNotice(form, closed);

  if (!closed) {
    ["School open", "Student activity allowed", "Student operational expectation", "Workforce operational expectation"].forEach((label) => {
      const control = findControlByLabel(form, label);
      if (control instanceof HTMLInputElement) control.disabled = false;
    });
    return;
  }

  setNativeValue(opensAt, "");
  setNativeValue(closesAt, "");
  setCheckbox(form, "School open", false);
  setCheckbox(form, "Student activity allowed", false);
  setCheckbox(form, "Student operational expectation", false);
  setCheckbox(form, "Workforce operational expectation", false);
};

function DayEditorStateBridge() {
  useEffect(() => {
    let frame = 0;

    const normalize = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const form = findDayEditorForm();
        if (form) normalizeClosedDay(form);
      });
    };

    const handleChange = (event) => {
      const form = event.target instanceof Element ? event.target.closest("form") : null;
      if (form?.textContent?.includes("Calendar day")) normalize();
    };

    const handleClick = (event) => {
      const button = event.target instanceof Element ? event.target.closest("button") : null;
      const form = button?.closest("form");
      if (form?.textContent?.includes("Calendar day")) normalize();
    };

    const observer = new MutationObserver(normalize);
    observer.observe(document.body, { childList: true, subtree: true, attributes: true });
    document.addEventListener("change", handleChange, true);
    document.addEventListener("click", handleClick, true);
    normalize();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener("change", handleChange, true);
      document.removeEventListener("click", handleClick, true);
    };
  }, []);

  return null;
}

export default DayEditorStateBridge;
