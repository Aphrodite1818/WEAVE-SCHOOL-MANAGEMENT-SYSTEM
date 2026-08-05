
import { LANDING_PRICING_PLANS } from "./subscriptionConfig";

const CATALOGUE_STORAGE_KEY = "weave:public-pricing-catalogue";
const CATALOGUE_CHANGED_EVENT = "weave:pricing-catalogue-changed";

const FEATURE_LABELS = {
  student_management: "Student management",
  teacher_management: "Teacher management",
  parent_portal: "Parent and student portals",
  academic_setup: "Academic lifecycle controls",
  report_cards: "Report cards",
  announcements: "Announcements",
  advanced_analytics: "Advanced analytics",
  bulk_import: "Bulk import enabled",
  bulk_academic_operations: "Bulk academic operations",
  tenant_branding: "School colour branding",
};

const NON_PUBLIC_FEATURES = new Set([
  "attendance",
  "geofencing",
  "ai_assistant",
]);

const formatCurrency = (amount, currency = "NGN") =>
  new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(amount || 0));

const unavailableLimits = () => ({
  students: null,
  teachers: null,
  parents: null,
  classes: null,
  subjects: null,
});

export const resetPublicPricingPlans = () => {
  LANDING_PRICING_PLANS.forEach((plan) => {
    plan.priceMonthly = null;
    plan.priceLabel = "Pricing unavailable";
    plan.features = [];
    plan.limits = unavailableLimits();
    plan.checkoutEnabled = false;
  });
  document.documentElement.dataset.pricingCatalogueReady = "false";
};

export const applyPublicPricingCatalogue = (catalogue, { persist = true } = {}) => {
  const plans = Array.isArray(catalogue?.plans) ? catalogue.plans : [];
  if (!plans.length) return false;

  const byCode = new Map(plans.map((plan) => [String(plan.plan_code), plan]));
  LANDING_PRICING_PLANS.forEach((presentation) => {
    const backendPlan = byCode.get(presentation.planCode);
    if (!backendPlan) return;

    const amount = Number(backendPlan.amount || 0);
    const prefix = presentation.planCode === "enterprise" ? "From " : "";
    const suffix = presentation.planCode === "free_trial" ? "" : "/mo";
    presentation.priceMonthly = amount;
    presentation.priceLabel = `${prefix}${formatCurrency(
      amount,
      backendPlan.currency || catalogue.currency || "NGN",
    )}${suffix}`;
    presentation.features = Object.entries(backendPlan.features || {})
      .filter(([feature, enabled]) => enabled === true && !NON_PUBLIC_FEATURES.has(feature))
      .map(([feature]) => FEATURE_LABELS[feature] || feature.replaceAll("_", " "));
    presentation.limits = {
      ...unavailableLimits(),
      ...(backendPlan.limits || {}),
    };
    presentation.checkoutEnabled = backendPlan.checkout_enabled === true;
  });

  document.documentElement.dataset.pricingCatalogueReady = "true";
  if (persist) {
    try {
      window.sessionStorage.setItem(CATALOGUE_STORAGE_KEY, JSON.stringify(catalogue));
    } catch {
      // Storage failure must not block pricing display.
    }
  }
  window.dispatchEvent(
    new CustomEvent(CATALOGUE_CHANGED_EVENT, {
      detail: { cacheVersion: catalogue.cache_version || null },
    }),
  );
  return true;
};

export const hydrateCachedPublicPricingCatalogue = () => {
  try {
    const cached = JSON.parse(
      window.sessionStorage.getItem(CATALOGUE_STORAGE_KEY) || "null",
    );
    return cached ? applyPublicPricingCatalogue(cached, { persist: false }) : false;
  } catch {
    window.sessionStorage.removeItem(CATALOGUE_STORAGE_KEY);
    return false;
  }
};
