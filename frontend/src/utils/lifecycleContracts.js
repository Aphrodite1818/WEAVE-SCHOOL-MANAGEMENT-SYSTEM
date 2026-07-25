export function normalizeMembershipSummary(membership = {}, fallback = {}) {
  return {
    membership_id:
      membership.membership_id || membership.id || fallback.membership_id || fallback.id || null,
    tenant_id: membership.tenant_id || fallback.tenant_id || null,
    tenant_name:
      membership.tenant_name ||
      membership.school_name ||
      fallback.tenant_name ||
      fallback.school_name ||
      "Unavailable school",
    tenant_logo_url:
      membership.tenant_logo_url ||
      membership.logo_url ||
      fallback.tenant_logo_url ||
      fallback.logo_url ||
      null,
    membership_status:
      membership.membership_status ||
      membership.status ||
      fallback.membership_status ||
      fallback.status ||
      "unknown",
    joined_at: membership.joined_at || fallback.joined_at || null,
    ended_at: membership.ended_at || fallback.ended_at || null,
  };
}

export function getBillingLifecycleLabel(daysUntilEnd, status) {
  if (daysUntilEnd === null || daysUntilEnd === undefined) {
    return "Renewal date pending";
  }
  const normalizedStatus = String(status || "").toLowerCase();
  if (daysUntilEnd < 0) {
    const elapsed = Math.abs(daysUntilEnd);
    if (["grace", "past_due", "overdue"].includes(normalizedStatus)) {
      return `${elapsed} day${elapsed === 1 ? "" : "s"} overdue`;
    }
    return `Ended ${elapsed} day${elapsed === 1 ? "" : "s"} ago`;
  }
  if (daysUntilEnd === 0) {
    return ["cancelled", "canceled"].includes(normalizedStatus)
      ? "Ends today"
      : "Renews today";
  }
  if (["cancelled", "canceled"].includes(normalizedStatus)) {
    return `Ends in ${daysUntilEnd} day${daysUntilEnd === 1 ? "" : "s"}`;
  }
  return `${daysUntilEnd} day${daysUntilEnd === 1 ? "" : "s"} left`;
}

export function toLocalDateInput(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function buildExplicitNullablePatch(form, optionalFields = []) {
  const nullable = new Set(optionalFields);
  return Object.fromEntries(
    Object.entries(form).map(([key, value]) => [
      key,
      nullable.has(key) && value === "" ? null : value,
    ]),
  );
}
