export const PUBLISHED_RESULT_STATUSES = new Set(["submitted", "published", "locked"]);

export const hasValue = (value) => value !== undefined && value !== null && value !== "";

export const asStatus = (value) => String(value || "").toLowerCase();

export const isPublishedResult = (result) => PUBLISHED_RESULT_STATUSES.has(asStatus(result?.status));

export const statusVariant = (status) => {
  const value = asStatus(status);
  if (["submitted", "published", "locked", "complete", "approved", "active"].includes(value)) return "success";
  if (["rejected", "failed", "declined"].includes(value)) return "error";
  if (["draft", "pending", "incomplete", "in_progress"].includes(value)) return "warning";
  return "info";
};

export const formatMetricNumber = (value) => {
  if (!hasValue(value)) return null;
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return value;
  return Number.isInteger(numericValue) ? numericValue : numericValue.toFixed(1);
};

export const scoreDisplayValue = (value) => {
  const formatted = formatMetricNumber(value);
  return formatted ?? "--";
};

export const displayStatusLabel = (value, fallback = "Pending") => {
  const text = hasValue(value) ? String(value) : fallback;
  return text.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
};

export const getAcademicContext = (results = [], reportCards = []) => {
  const latestResult = results[0];
  const latestReportCard = reportCards[0];
  const source = latestResult || latestReportCard || {};

  return {
    classLabel: source.class_name || null,
    sessionLabel: source.academic_session_name || null,
    termLabel: source.academic_term_name || null,
  };
};
