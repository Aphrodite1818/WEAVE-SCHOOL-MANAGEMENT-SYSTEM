export const PLAN_DISPLAY_NAMES = {
  free: "Free",
  free_trial: "Free",
  plus: "Plus",
  professional: "Professional",
  enterprise: "Enterprise",
};

export const PLAN_ORDER = ["free", "plus", "professional", "enterprise"];

export const BILLING_INTERVAL_LABELS = {
  term: "Per academic term",
};

export const FEATURE_CODES = {
  STUDENT_MANAGEMENT: "student_management",
  TEACHER_MANAGEMENT: "teacher_management",
  PARENT_PORTAL: "parent_portal",
  ACADEMIC_SETUP: "academic_setup",
  REPORT_CARDS: "report_cards",
  ANNOUNCEMENTS: "announcements",
  ADVANCED_ANALYTICS: "advanced_analytics",
  AI_ASSISTANT: "ai_assistant",
  BULK_IMPORT: "bulk_import",
  TENANT_BRANDING: "tenant_branding",
  CBT_PAIRING: "cbt_pairing",
};

export const RESOURCE_CODES = {
  STUDENTS: "students",
  TEACHERS: "teachers",
  PARENTS: "parents",
  CBT_SERVERS: "cbt_servers",
};

export const SUBSCRIPTION_STATUS_META = {
  trialing: {
    label: "Free",
    message: "Your school is using the permanent Free plan.",
    badgeVariant: "default",
  },
  active: {
    label: "Active",
    message: "Your current academic term plan is active.",
    badgeVariant: "success",
  },
  expired: {
    label: "Free",
    message: "Your school can continue on the permanent Free plan.",
    badgeVariant: "default",
  },
};

export const BILLING_INTERVAL_OPTIONS = [
  { value: "term", label: "Per academic term" },
];

export const LANDING_PRICING_PLANS = [
  {
    planCode: "free",
    name: "Free",
    bestFor: "Best for smaller school operations",
    description:
      "Use Weave permanently with core school workflows and deliberately limited capacity.",
    pricePerTerm: 0,
    priceLabel: "₦0",
    features: [],
    limits: {},
    checkoutEnabled: false,
    ctaLabel: "Get started",
  },
  {
    planCode: "plus",
    name: "Plus",
    bestFor: "Best for smaller schools",
    description:
      "More capacity and operational tools for schools ready to run broader day-to-day workflows in Weave.",
    pricePerTerm: null,
    priceLabel: "Pricing unavailable",
    features: [],
    limits: {},
    checkoutEnabled: false,
    ctaLabel: "Get started",
  },
  {
    planCode: "professional",
    name: "Professional",
    bestFor: "Best for growing schools",
    description:
      "Greater capacity plus premium operational capabilities for established schools.",
    pricePerTerm: null,
    priceLabel: "Pricing unavailable",
    features: [],
    limits: {},
    checkoutEnabled: false,
    ctaLabel: "Get started",
    highlighted: true,
  },
  {
    planCode: "enterprise",
    name: "Enterprise",
    bestFor: "Best for larger schools",
    description:
      "Maximum capacity and premium capabilities for large school operations.",
    pricePerTerm: null,
    priceLabel: "Pricing unavailable",
    features: [],
    limits: {},
    checkoutEnabled: false,
    ctaLabel: "Get started",
  },
];

const SUBSCRIPTION_SELECTION_STORAGE_KEY = "weave_subscription_selection";

const ATTENTION_STATUSES = new Set();

const canonicalPlanCode = (value) => {
  const normalized = String(value || "")
    .trim()
    .toLowerCase();
  if (normalized === "free_trial") return "free";
  return PLAN_ORDER.includes(normalized) ? normalized : "free";
};

const canonicalBillingInterval = () => "term";

export const formatPlanName = (planCode) =>
  PLAN_DISPLAY_NAMES[canonicalPlanCode(planCode)] || "Free";

export const formatBillingInterval = () =>
  BILLING_INTERVAL_LABELS.term || "Per academic term";

export const getSubscriptionStatusMeta = (status) =>
  SUBSCRIPTION_STATUS_META[String(status || "").toLowerCase()] || {
    label: "Active",
    message: "Your school can use Weave within its current plan limits.",
    badgeVariant: "default",
  };

export const isAttentionStatus = (status) =>
  ATTENTION_STATUSES.has(String(status || "").toLowerCase());

export const formatDateTime = (value, options = {}) => {
  if (!value) return "--";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    ...options,
  });
};

export const formatLimitValue = (value) => {
  if (value === null) return "Unlimited";
  if (value === undefined) return "—";
  return String(value);
};

export const formatUsageValue = (usage) => {
  if (!usage) return "--";
  if (usage.is_unlimited) return "Unlimited";
  return `${usage.used} / ${usage.limit ?? 0}`;
};

export const buildRegistrationHref = (planCode) => {
  const nextPlanCode = canonicalPlanCode(planCode);
  const params = new URLSearchParams({
    plan: nextPlanCode,
    billing: "term",
  });
  return `/register?${params.toString()}`;
};

export const saveSelectedSubscriptionPlan = ({
  planCode,
  billingInterval = "term",
} = {}) => {
  if (typeof window === "undefined") return;

  const payload = {
    planCode: canonicalPlanCode(planCode),
    billingInterval: canonicalBillingInterval(billingInterval),
  };

  window.sessionStorage.setItem(
    SUBSCRIPTION_SELECTION_STORAGE_KEY,
    JSON.stringify(payload),
  );
};

export const getSelectedSubscriptionPlan = () => {
  if (typeof window === "undefined") return null;

  try {
    const rawValue = window.sessionStorage.getItem(
      SUBSCRIPTION_SELECTION_STORAGE_KEY,
    );
    if (!rawValue) return null;

    const parsed = JSON.parse(rawValue);
    return {
      planCode: canonicalPlanCode(parsed?.planCode),
      billingInterval: "term",
    };
  } catch {
    return null;
  }
};

export const clearSelectedSubscriptionPlan = () => {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(SUBSCRIPTION_SELECTION_STORAGE_KEY);
};
