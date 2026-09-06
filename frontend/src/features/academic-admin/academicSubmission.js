// Lock synchronously: React's pending render alone cannot prevent a second submit.
const pendingForms = new WeakSet();

export function beginAcademicSubmission(event, pending = false) {
  event.preventDefault();
  const form = event.currentTarget;
  if (pending || pendingForms.has(form)) return null;
  pendingForms.add(form);
  return {
    form,
    addAnother: event.nativeEvent?.submitter?.value !== "close",
  };
}

export function endAcademicSubmission(submission) {
  pendingForms.delete(submission.form);
  if (submission.focusAfterSave) {
    requestAnimationFrame(() => {
      submission.form.querySelector(
        '[data-create-focus], input:not([type="hidden"]):not([disabled]), button[role="combobox"]',
      )?.focus();
    });
  }
}

export function finishAcademicCreation(submission, reset, close, editing = false) {
  if (editing || !submission.addAnother) {
    close();
    return;
  }
  reset();
  submission.focusAfterSave = true;
}
