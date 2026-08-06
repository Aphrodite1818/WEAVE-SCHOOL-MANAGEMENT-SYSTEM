import { useEffect } from "react";

const CLOSED_DAY_TYPES = new Set([
  "weekend",
  "public_holiday",
  "school_holiday",
  "mid_term_break",
  "emergency_closure",
]);

const normalizeText = (value) => String(value || "").trim().toLowerCase();

const fieldByLabel = (root, labelText) => {
  const target = normalizeText(labelText);
  const label = Array.from(root.querySelectorAll("label")).find((item) =>
    normalizeText(item.textContent).includes(target),
  );
  if (!label) return null;

  const forId = label.getAttribute("for");
  if (forId) return root.querySelector(`#${CSS.escape(forId)}`);

  return (
    label.querySelector("input, select, textarea") ||
    label.parentElement?.querySelector("input, select, textarea") ||
    null
  );
};

const setControlledValue = (element, value) => {
  if (!(element instanceof HTMLInputElement || element instanceof HTMLSelectElement)) return false;
  if (element.value === value) return false;

  const prototype = element instanceof HTMLInputElement
    ? HTMLInputElement.prototype
    : HTMLSelectElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(element, value);
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
};

const setCheckbox = (root, labelText, checked) => {
  const input = fieldByLabel(root, labelText);
  if (!(input instanceof HTMLInputElement) || input.type !== "checkbox") return false;
  if (input.checked === checked) return false;
  input.click();
  return true;
};

const fieldContainer = (element) =>
  element?.closest("label")?.parentElement ||
  element?.parentElement?.parentElement ||
  element?.closest("div") ||
  null;

const setFieldVisibility = (element, visible) => {
  const container = fieldContainer(element);
  if (!container) return;

  container.hidden = !visible;
  container.style.display = visible ? "" : "none";
  container.setAttribute("aria-hidden", String(!visible));

  if (element instanceof HTMLInputElement) {
    element.disabled = !visible;
    element.required = visible;
  }
};

const ensureHoursNotice = (form, visible) => {
  let notice = form.querySelector("[data-closed-day-hours-notice]");
  if (!notice) {
    notice = document.createElement("div");
    notice.dataset.closedDayHoursNotice = "true";
    notice.className = "rounded-2xl border border-border/70 bg-surface-muted px-4 py-3 text-sm text-text-muted sm:col-span-2";
    notice.textContent = "Operating hours not applicable. This day is closed, so opening and closing times will be saved as empty.";
    fieldContainer(fieldByLabel(form, "Closes at"))?.insertAdjacentElement("afterend", notice);
  }
  notice.hidden = !visible;
  notice.style.display = visible ? "" : "none";
};

const normalizeEditor = (form) => {
  const dayType = fieldByLabel(form, "Day type");
  if (!(dayType instanceof HTMLSelectElement)) return { closed: false, changed: false };

  const opensAt = fieldByLabel(form, "Opens at");
  const closesAt = fieldByLabel(form, "Closes at");
  const closed = CLOSED_DAY_TYPES.has(dayType.value);

  setFieldVisibility(opensAt, !closed);
  setFieldVisibility(closesAt, !closed);
  ensureHoursNotice(form, closed);

  if (!closed) return { closed: false, changed: false };

  const changed = [
    setControlledValue(opensAt, ""),
    setControlledValue(closesAt, ""),
    setCheckbox(form, "School open", false),
    setCheckbox(form, "Student activity allowed", false),
    setCheckbox(form, "Student operational expectation", false),
    setCheckbox(form, "Workforce operational expectation", false),
  ].some(Boolean);

  return { closed: true, changed };
};

const findDayEditorForm = () =>
  Array.from(document.querySelectorAll("form")).find((form) =>
    form.textContent?.includes("Calendar day"),
  );

const scheduleNormalization = (form) => {
  queueMicrotask(() => normalizeEditor(form));
  window.requestAnimationFrame(() => normalizeEditor(form));
  window.setTimeout(() => normalizeEditor(form), 0);
  window.setTimeout(() => normalizeEditor(form), 50);
};

function ClosedDayEditorBehavior() {
  useEffect(() => {
    let activeForm = null;
    let cleanup = () => {};
    const resubmitting = new WeakSet();

    const bind = () => {
      const nextForm = findDayEditorForm();
      if (nextForm === activeForm) return;

      cleanup();
      activeForm = nextForm || null;
      if (!activeForm) return;

      const handleInteraction = () => scheduleNormalization(activeForm);
      const handleSubmit = (event) => {
        if (resubmitting.has(activeForm)) {
          resubmitting.delete(activeForm);
          return;
        }

        const result = normalizeEditor(activeForm);
        if (!result.closed || !result.changed) return;

        event.preventDefault();
        resubmitting.add(activeForm);
        window.setTimeout(() => activeForm?.requestSubmit(), 0);
      };

      activeForm.addEventListener("change", handleInteraction, true);
      activeForm.addEventListener("input", handleInteraction, true);
      activeForm.addEventListener("click", handleInteraction, true);
      activeForm.addEventListener("submit", handleSubmit, true);
      scheduleNormalization(activeForm);

      cleanup = () => {
        activeForm?.removeEventListener("change", handleInteraction, true);
        activeForm?.removeEventListener("input", handleInteraction, true);
        activeForm?.removeEventListener("click", handleInteraction, true);
        activeForm?.removeEventListener("submit", handleSubmit, true);
      };
    };

    const observer = new MutationObserver(() => {
      bind();
      if (activeForm) scheduleNormalization(activeForm);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    bind();

    return () => {
      observer.disconnect();
      cleanup();
    };
  }, []);

  return null;
}

export default ClosedDayEditorBehavior;
