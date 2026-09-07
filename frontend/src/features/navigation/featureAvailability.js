import { FEATURE_CODES } from "../subscriptions/subscriptionConfig.js";

const normalizedPlanCode = (subscription) =>
  String(subscription?.planCode || "").trim().toLowerCase();

export function resolveFeatureAvailability(
  item,
  {
    runtimeFeatures = {},
    entitledFeatures,
    subscription,
    isAccountScope = false,
  } = {},
) {
  if (!item) return { visible: false, reason: "missing-item" };

  if (isAccountScope && !item.accountScope) {
    return { visible: false, reason: "tenant-workspace-required" };
  }

  if (
    item.runtimeFeature &&
    runtimeFeatures?.[item.runtimeFeature] === false
  ) {
    return { visible: false, reason: "runtime-disabled" };
  }

  const featureCode = item.featureCode || item.feature || null;
  if (!featureCode) return { visible: true, reason: null };

  if (
    featureCode === FEATURE_CODES.BULK_IMPORT &&
    normalizedPlanCode(subscription) === "free_trial"
  ) {
    return { visible: false, reason: "plan-disabled" };
  }

  const getFeatureGuard = subscription?.getFeatureGuard;
  if (typeof getFeatureGuard === "function") {
    const guard = getFeatureGuard(featureCode);
    if (guard?.pending) return { visible: false, reason: "entitlement-pending" };
    if (guard?.allowed === false) {
      return { visible: false, reason: guard.reason || "entitlement-disabled" };
    }
  } else if (item.feature && entitledFeatures?.[featureCode] !== true) {
    // Legacy guide steps using `feature` are opt-in: absence is not entitlement.
    return { visible: false, reason: "entitlement-disabled" };
  } else if (entitledFeatures?.[featureCode] === false) {
    return { visible: false, reason: "entitlement-disabled" };
  }

  return { visible: true, reason: null };
}

export function isFeatureAvailable(item, context) {
  return resolveFeatureAvailability(item, context).visible;
}

export function filterAvailableItems(items = [], context) {
  return items.filter((item) => isFeatureAvailable(item, context));
}
