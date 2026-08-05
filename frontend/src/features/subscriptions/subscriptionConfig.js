export const PLAN_DISPLAY_NAMES = {
  free_trial: "Free Trial",
  plus: "Plus",
  professional: "Professional",
  enterprise: "Enterprise",
};

export const PLAN_ORDER = ["free_trial", "plus", "professional", "enterprise"];

export const BILLING_INTERVAL_LABELS = {
  monthly: "Monthly",
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
};

export const RESOURCE_CODES = {
  STUDENTS: "students",
  TEACHERS: "teachers",
  PARENTS: "parents",
  CLASSES: "classes",
  SUBJECTS: "subjects",
};

export const SUBSCRIPTION_STATUS_META = {
  trialing: {
    label: "Trial Active",
    message: "Your 30-day free trial is active.",
    badgeVariant: "info",
  },
  active: {
    label: "Active",
    message: "Your monthly subscription is active.",
    badgeVariant: "success",
  },
  non_renewing: {
    label: "Cancels at Period End",
    message: "Your subscription remains active until the end of the current billing period.",
    badgeVariant: "warning",
  },
  past_due: {
    label: "Payment Issue",
    message: "We could not process your latest payment.",
    badgeVariant: "error",
  },
  grace_period: {
    label: "Grace Period",
    message: "Your subscription is in grace period. Update billing before read-only restrictions begin.",
    badgeVariant: "warning",
  },
  expired: {
    label: "Read-only",
    message: "Your subscription has expired. Billing remains available, but write actions are restricted.",
    badgeVariant: "error",
  },
  cancelled: {
    label: "Cancelled",
    message: "Your subscription has been cancelled.",
    badgeVariant: "default",
  },
};

export const BILLING_INTERVAL_OPTIONS = [
  { value: "monthly", label: "Monthly" },
];

export const LANDING_PRICING_PLANS = [
  {
    planCode: "free_trial",
    name: "Free Trial",
    bestFor: "Best for exploring Weave",
    description: "Experience the core Weave workflow and see how a connected school workspace fits your operations before subscribing.",
    priceMonthly: null,
    priceLabel: "Pricing unavailable",
    features: [],
    limits: {},
    checkoutEnabled: false,
    ctaLabel: "Start Free Trial",
  },
  {
    planCode: "plus",
    name: "Plus",
    bestFor: "Best for smaller schools",
    description: "A complete starting point for schools ready to organise students, staff, academic records, portals, and everyday administration in one place.",
    priceMonthly: null,
    priceLabel: "Pricing unavailable",
    features: [],
    limits: {},
    checkoutEnabled: false,
    ctaLabel: "Choose Plus",
  },
  {
    planCode: "professional",
    name: "Professional",
    bestFor: "Best for growing schools",
    description: "Greater capacity for established schools managing more students, teachers, classes, records, and operational complexity.",
    priceMonthly: null,
    priceLabel: "Pricing unavailable",
    features: [],
    limits: {},
    checkoutEnabled: false,
    ctaLabel: "Choose Professional",
    highlighted: true,
  },
  {
    planCode: "enterprise",
    name: "Enterprise",
    bestFor: "Best for larger schools",
    description: "Designed for large school operations that need maximum capacity, flexible resource limits, and priority support readiness.",
    priceMonthly: null,
    priceLabel: "Pricing unavailable",
    features: [],
    limits: {},
    checkoutEnabled: false,
    ctaLabel: "Choose Enterprise",
  },
];

const SUBSCRIPTION_SELECTION_STORAGE_KEY = "weave_subscription_selection";
const REGISTRATION_CHECKOUT_STORAGE_KEY = "weave_registration_checkout_intent";
const REGISTRATION_CHECKOUT_REDIRECT_KEY = "weave_registration_checkout_redirect";

const ATTENTION_STATUSES = new Set([
  "past_due",
  "grace_period",
  "expired",
  "cancelled",
]);

const canonicalPlanCode = (value) => {
  const normalized = String(value || "").trim().toLowerCase();
  return PLAN_DISPLAY_NAMES[normalized] ? normalized : "free_trial";
};

const canonicalBillingInterval = () => "monthly";

export const formatPlanName = (planCode) =>
  PLAN_DISPLAY_NAMES[canonicalPlanCode(planCode)] || "Free Trial";

export const formatBillingInterval = () =>
  BILLING_INTERVAL_LABELS.monthly || "Monthly";

export const getSubscriptionStatusMeta = (status) =>
  SUBSCRIPTION_STATUS_META[String(status || "").toLowerCase()] || {
    label: "Unknown",
    message: "We could not determine your current subscription state.",
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

export const formatLimitValue = (value) =>
  value === null || value === undefined ? "Unlimited" : String(value);

export const formatUsageValue = (usage) => {
  if (!usage) return "--";
  if (usage.is_unlimited) return "Unlimited";
  return `${usage.used} / ${usage.limit ?? 0}`;
};

export const buildRegistrationHref = (planCode) => {
  const nextPlanCode = canonicalPlanCode(planCode);
  const params = new URLSearchParams({ plan: nextPlanCode });

  if (nextPlanCode !== "free_trial") {
    params.set("billing", "monthly");
  }

  return `/register?${params.toString()}`;
};

export const saveSelectedSubscriptionPlan = ({
  planCode,
  billingInterval = "monthly",
} = {}) => {
  if (typeof window === "undefined") return;

  const payload = {
    planCode: canonicalPlanCode(planCode),
    billingInterval: canonicalBillingInterval(billingInterval),
  };

  window.sessionStorage.setItem(
    SUBSCRIPTION_SELECTION_STORAGE_KEY,
    JSON.stringify(payload)
  );
};

export const getSelectedSubscriptionPlan = () => {
  if (typeof window === "undefined") return null;

  try {
    const rawValue = window.sessionStorage.getItem(
      SUBSCRIPTION_SELECTION_STORAGE_KEY
    );

    if (!rawValue) return null;

    const parsed = JSON.parse(rawValue);

    return {
      planCode: canonicalPlanCode(parsed?.planCode),
      billingInterval: "monthly",
    };
  } catch {
    return null;
  }
};

export const clearSelectedSubscriptionPlan = () => {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(SUBSCRIPTION_SELECTION_STORAGE_KEY);
};

export const saveRegistrationCheckoutIntent = ({
  planCode,
  billingInterval = "monthly",
} = {}) => {
  if (typeof window === "undefined") return;

  const nextPlanCode = canonicalPlanCode(planCode);
  if (nextPlanCode === "free_trial") {
    window.sessionStorage.removeItem(REGISTRATION_CHECKOUT_STORAGE_KEY);
    return;
  }

  window.sessionStorage.setItem(
    REGISTRATION_CHECKOUT_STORAGE_KEY,
    JSON.stringify({
      planCode: nextPlanCode,
      billingInterval: canonicalBillingInterval(billingInterval),
    }),
  );
};

export const getRegistrationCheckoutIntent = (user = {}) => {
  const tenantFlags = user?.tenant?.feature_flags || user?.feature_flags || {};
  const tenantPlanCode = canonicalPlanCode(
    tenantFlags.registration_selected_plan_code ||
      tenantFlags.selected_plan_code ||
      tenantFlags.registration_plan_code,
  );
  const tenantBillingInterval =
    tenantFlags.registration_billing_interval || "monthly";

  if (tenantPlanCode !== "free_trial") {
    return {
      planCode: tenantPlanCode,
      billingInterval: canonicalBillingInterval(tenantBillingInterval),
      source: "tenant",
    };
  }

  if (typeof window === "undefined") return null;

  try {
    const parsed = JSON.parse(
      window.sessionStorage.getItem(REGISTRATION_CHECKOUT_STORAGE_KEY) || "null",
    );
    const planCode = canonicalPlanCode(parsed?.planCode);
    if (planCode === "free_trial") return null;
    return {
      planCode,
      billingInterval: canonicalBillingInterval(parsed?.billingInterval),
      source: "session",
    };
  } catch {
    window.sessionStorage.removeItem(REGISTRATION_CHECKOUT_STORAGE_KEY);
    return null;
  }
};

export const clearRegistrationCheckoutIntent = () => {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(REGISTRATION_CHECKOUT_STORAGE_KEY);
};

export const markRegistrationCheckoutRedirect = (intent) => {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(
    REGISTRATION_CHECKOUT_REDIRECT_KEY,
    JSON.stringify({
      planCode: canonicalPlanCode(intent?.planCode),
      createdAt: new Date().toISOString(),
    }),
  );
};

export const consumeRegistrationCheckoutRedirect = () => {
  if (typeof window === "undefined") return null;

  try {
    const parsed = JSON.parse(
      window.sessionStorage.getItem(REGISTRATION_CHECKOUT_REDIRECT_KEY) || "null",
    );
    window.sessionStorage.removeItem(REGISTRATION_CHECKOUT_REDIRECT_KEY);
    return parsed;
  } catch {
    window.sessionStorage.removeItem(REGISTRATION_CHECKOUT_REDIRECT_KEY);
    return null;
  }
};