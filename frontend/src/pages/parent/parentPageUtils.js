export const PARENT_SELECTED_CHILD_KEY = "parent-selected-child-id";

export function normalizeParentChildRecord(entry) {
  if (!entry || typeof entry !== "object") {
    return { student: null, link: {} };
  }

  return {
    student: entry.student || entry,
    link: entry.link || entry.parent_link || {},
  };
}

export function getParentChildId(entry) {
  return normalizeParentChildRecord(entry).student?.id || "";
}

export function readSelectedChildId(children = []) {
  if (typeof window === "undefined") {
    return getParentChildId(children[0]);
  }

  const stored = sessionStorage.getItem(PARENT_SELECTED_CHILD_KEY);
  if (stored && children.some((item) => getParentChildId(item) === stored)) {
    return stored;
  }

  return getParentChildId(children[0]);
}

export function writeSelectedChildId(childId) {
  if (typeof window === "undefined") return;

  if (childId) {
    sessionStorage.setItem(PARENT_SELECTED_CHILD_KEY, childId);
  } else {
    sessionStorage.removeItem(PARENT_SELECTED_CHILD_KEY);
  }
}
