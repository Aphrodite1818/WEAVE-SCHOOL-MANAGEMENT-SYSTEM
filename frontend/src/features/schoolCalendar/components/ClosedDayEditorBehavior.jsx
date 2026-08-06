import { useEffect } from "react";

const CLOSED_DAY_TYPES = new Set([
  "weekend",
  "public_holiday",
  "school_holiday",
  "mid_term_break",
  "emergency_closure",
]);

const fieldByLabel = (root, labelText) => {
  const labels = Array.from(root.querySelectorAll("label"));
  const label = labels.find(
    (item) => item.textContent?.trim().toLowerCase() === labelText.toLowerCase(),
  );
  if (!label) return null;
  const forId = label.getAttribute("for");
  if (forId) return root.querySelector(`#${CSS.escape(forId)}`);
  return label.querySelector("input, select, textarea") || label.parentElement?.querySelector("input, select, textarea");
};

const setControlledValue = (element, value) => {
  if (!element) return;
  const prototype = Object.getPrototypeOf(element);
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
  descriptor?.set?.call(element, value);
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
};

const setCheckbox = (root, labelText, checked) => {
  const input = fieldByLabel(root, labelText);
  if (input instanceof HTMLInputElement && input.type === "checkbox" && input.checked !== checked) {
    input.click();
  }
};

const setFieldVisibility = (element, visible) => {
  const container = element?.closest("div");
  if (!container) return;
  container.hidden = !visible;
  container.setAttribute("aria-hidden", String(!visible));
};

const ensureClosureNotice = (form) => {
  if (form.querySelector("[data-closure-workflow-notice]")) return;
  const notice = document.createElement("div");
  notice.dataset.closureWorkflowNotice = "true";
  notice.className = "mt-4 rounded-2xl border border-warning/40 bg-warning-soft px-4 py-3 text-sm text-amber-950";
  notice.textContent = "Emergency closures are managed from the Closures page so one date or an entire date range follows the same audited workflow.";
  const dayType = fieldByLabel(form, "Day type");
  dayType?.closest("div")?.parentElement?.insertAdjacentElement("afterend", notice);
};

const restrictEmergencyClosureOption = (dayType) => {
  if (!(dayType instanceof HTMLSelectElement)) return;
  const option = Array.from(dayType.options).find((item) => item.value === "emergency_closure");
  if (!option) return;

  if (dayType.value === "emergency_closure") {
    option.disabled = true;
    option.textContent = "Emergency closure — managed in Closures";
    return;
  }

  option.remove();
};

const normalizeEditor = (form) => {
  const dayType = fieldByLabel(form, "Day type");
  if (!(dayType instanceof HTMLSelectElement)) return;

  restrictEmergencyClosureOption(dayType);
  ensureClosureNotice(form);

  const opensAt = fieldByLabel(form, "Opens at");
  const closesAt = fieldByLabel(form, "Closes at");
  const isClosedDay = CLOSED_DAY_TYPES.has(dayType.value);

  setFieldVisibility(opensAt, !isClosedDay);
  setFieldVisibility(closesAt, !isClosedDay);

  if (!isClosedDay) return;

  setControlledValue(opensAt, "");
  setControlledValue(closesAt, "");
  setCheckbox(form, "School open", false);
  setCheckbox(form, "Student activity allowed", false);
  setCheckbox(form, "Student operational expectation", false);
  setCheckbox(form, "Workforce operational expectation", false);
};

const findDayEditorForm = () =>
  Array.from(document.querySelectorAll("form")).find((form) =>
    form.textContent?.includes("Calendar day"),
  );

function ClosedDayEditorBehavior() {
  useEffect(() => {
    let activeForm = null;
    let cleanupActiveForm = () => {};

    const bind = () => {
      const nextForm = findDayEditorForm();
      if (nextForm === activeForm) return;

      cleanupActiveForm();
      activeForm = nextForm || null;
      if (!activeForm) return;

      const handleChange = (event) => {
        if (event.target instanceof HTMLSelectElement) normalizeEditor(activeForm);
      };
      const handleSubmit = () => normalizeEditor(activeForm);

      activeForm.addEventListener("change", handleChange);
      activeForm.addEventListener("submit", handleSubmit, true);
      normalizeEditor(activeForm);

      cleanupActiveForm = () => {
        activeForm?.removeEventListener("change", handleChange);
        activeForm?.removeEventListener("submit", handleSubmit, true);
      };
    };

    const observer = new MutationObserver(bind);
    observer.observe(document.body, { childList: true, subtree: true });
    bind();

    return () => {
      observer.disconnect();
      cleanupActiveForm();
    };
  }, []);

  return null;
}

export default ClosedDayEditorBehavior;
