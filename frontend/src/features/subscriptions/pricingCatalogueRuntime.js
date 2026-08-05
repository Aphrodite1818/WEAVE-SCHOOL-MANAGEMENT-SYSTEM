import { LANDING_PRICING_PLANS } from "./subscriptionConfig";

const FEATURE_LABELS = {
  student_management: "Student management",
  teacher_management: "Teacher management",
  parent_portal: "Parent and student portals",
  academic_setup: "Academic lifecycle controls",
  report_cards: "Report cards",
  announcements: "Announcements",
  attendance: "Attendance management",
  geofencing: "Attendance geofencing",
  advanced_analytics: "Advanced analytics",
  ai_assistant: "AI assistant",
  bulk_import: "Bulk import enabled",
  bulk_academic_operations: "Bulk academic operations",
  tenant_branding: "School colour branding",
};

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

export const applyPublicPricingCatalogue = (catalogue) => {
  const plans = Array.isArray(catalogue?.plans) ? catalogue.plans : [];
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
      .filter(([, enabled]) => enabled === true)
      .map(([feature]) => FEATURE_LABELS[feature] || feature.replaceAll("_", " "));
    presentation.limits = {
      ...unavailableLimits(),
      ...(backendPlan.limits || {}),
    };
    presentation.checkoutEnabled = backendPlan.checkout_enabled === true;
  });

  document.documentElement.dataset.pricingCatalogueReady = "true";
};
