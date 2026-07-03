export const AVATAR_SRC_KEYS = [
  "profile_image_url",
  "avatar_url",
  "image_url",
  "photo_url",
  "passport_photo_url",
];

export function fullName(user) {
  return (
    [user?.first_name || user?.firstname, user?.last_name || user?.lastname]
      .filter(Boolean)
      .join(" ") || ""
  );
}

export function displayName(user) {
  return fullName(user) || user?.admission_number || user?.email || "User";
}

export function schoolName(tenant) {
  return (
    tenant?.school_name?.trim?.() ||
    tenant?.schoolName?.trim?.() ||
    tenant?.tenant?.school_name?.trim?.() ||
    tenant?.tenant?.schoolName?.trim?.() ||
    tenant?.tenant?.name?.trim?.() ||
    tenant?.name?.trim?.() ||
    "School workspace"
  );
}

export function getUserDisplayName(user) {
  return displayName(user);
}

export function getUserInitials(user) {
  const firstInitial = String(user?.first_name || user?.firstname || "").trim().charAt(0);
  const lastInitial = String(user?.last_name || user?.lastname || "").trim().charAt(0);
  const initials = `${firstInitial}${lastInitial}`.trim().toUpperCase();

  if (initials) return initials;

  return String(user?.admission_number || user?.email || "U").trim().charAt(0).toUpperCase() || "U";
}

export function getUserAvatarSrc(user) {
  return getAvatarSrcFromRecord(user);
}

export function getAvatarSrcFromRecord(record) {
  if (!record) return undefined;

  for (const key of AVATAR_SRC_KEYS) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }

  return undefined;
}
