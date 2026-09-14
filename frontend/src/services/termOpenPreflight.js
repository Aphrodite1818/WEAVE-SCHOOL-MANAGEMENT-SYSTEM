const asItems = (response) =>
  Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

const termLabel = (value) =>
  String(value || "academic term")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export const activeTermOpenBlocker = (response, targetTermId) => {
  const targetId = String(targetTermId || "");
  const activeTerm = asItems(response).find(
    (item) =>
      String(item?.id || "") !== targetId &&
      item?.is_current === true &&
      ["open", "closing"].includes(String(item?.status || "").toLowerCase()),
  );

  if (!activeTerm) return null;

  return `${termLabel(activeTerm.name)} is currently active. Close it before opening another academic term.`;
};

export const dependencyOpenBlocker = (preview) => {
  if (!preview || preview.can_open === true) return null;
  const messages = Array.isArray(preview?.blocker_messages)
    ? preview.blocker_messages.filter(Boolean)
    : [];
  return messages.join(" ") || "This academic term is not ready to open yet.";
};

export const termOpenPreflightBlocker = ({
  currentTerms,
  targetTermId,
  dependencyPreview,
} = {}) =>
  activeTermOpenBlocker(currentTerms, targetTermId) ||
  dependencyOpenBlocker(dependencyPreview);
