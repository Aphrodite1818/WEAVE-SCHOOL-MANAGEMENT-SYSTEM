export function termEntitlementLabel(entitlement, term) {
  if (entitlement.status !== "active") return entitlement.status.replaceAll("_", " ");
  if (term?.status === "draft") return "Purchased · Scheduled";
  if (term?.status === "open" && term.is_current) return "Active for current term";
  return "Purchased for this term";
}
