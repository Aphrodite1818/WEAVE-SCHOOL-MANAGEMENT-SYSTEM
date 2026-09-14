export function shouldShowUsage(usage) {
  if (!usage) return false;
  if (Number(usage.used) > 0) return true;
  return usage.is_unlimited === true || usage.limit === null || Number(usage.limit) > 0;
}
