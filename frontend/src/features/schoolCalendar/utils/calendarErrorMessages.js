import { parseApiError } from "../../../services/api";

const FIELD_LABELS = {
  reason: "reason",
  description: "description",
  title: "title",
};

const friendlyMinimumLengthMessage = (field) => {
  const label = FIELD_LABELS[field] || "value";
  return `Please enter at least 3 characters for the ${label}.`;
};

export const getCalendarErrorMessage = (error, fallback) => {
  const parsed = parseApiError(error, fallback);
  const fieldErrors = parsed.fieldErrors || {};

  for (const [field, message] of Object.entries(fieldErrors)) {
    if (/at least 3 characters|min_length|too short/i.test(message)) {
      return friendlyMinimumLengthMessage(field.split(".").pop());
    }
  }

  if (
    /at least 3 characters|min_length|too short/i.test(parsed.message || "")
  ) {
    return "Please review the highlighted calendar fields and enter at least 3 characters where required.";
  }

  return parsed.message;
};
