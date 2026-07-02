export const PARENT_SELECTED_CHILD_KEY = "parent-selected-child-id";

export function readSelectedChildId(children = []) {
  if (typeof window === "undefined") {
    return children[0]?.student?.id || "";
  }

  const stored = sessionStorage.getItem(PARENT_SELECTED_CHILD_KEY);
  if (stored && children.some((item) => item.student?.id === stored)) {
    return stored;
  }

  return children[0]?.student?.id || "";
}

export function writeSelectedChildId(childId) {
  if (typeof window === "undefined") return;

  if (childId) {
    sessionStorage.setItem(PARENT_SELECTED_CHILD_KEY, childId);
  } else {
    sessionStorage.removeItem(PARENT_SELECTED_CHILD_KEY);
  }
}
