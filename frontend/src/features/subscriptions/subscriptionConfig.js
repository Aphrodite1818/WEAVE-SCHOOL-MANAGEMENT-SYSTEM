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
    bestFor: "Best for testing LearnlyAI",
    description: "Try the core school workflow for 30 days before moving into monthly billing.",
    priceMonthly: 0,
    priceLabel: "₦0",
    features: [
      "30-day trial",
      "Core academic setup",
      "Basic report cards",
      "No advanced analytics",
    ],
    limits: {
      students: 50,
      teachers: 10,
      parents: 50,
      classes: 10,
      subjects: 20,
    },
    ctaLabel: "Start Free Trial",
  },
  {
    planCode: "plus",
    name: "Plus",
    bestFor: "Best for small schools",
    description: "A practical paid plan for small schools that need the full daily workflow.",
    priceMonthly: 15000,
    priceLabel: "₦15,000/mo",
    features: [
      "Advanced analytics",
      "AI assistant enabled",
      "Bulk import enabled",
      "Parent and student portals",
    ],
    limits: {
      students: 300,
      teachers: 30,
      parents: 300,
      classes: 30,
      subjects: 60,
    },
    ctaLabel: "Choose Plus",
  },
  {
    planCode: "professional",
    name: "Professional",
    bestFor: "Best for growing schools",
    description: "Higher capacity for schools managing more staff, classes, and records.",
    priceMonthly: 35000,
    priceLabel: "₦35,000/mo",
    features: [
      "Advanced analytics",
      "AI assistant enabled",
      "Bulk import enabled",
      "Higher school limits",
    ],
    limits: {
      students: 1000,
      teachers: 100,
      parents: 1000,
      classes: 100,
      subjects: 150,
    },
    ctaLabel: "Choose Professional",
    highlighted: true,
  },
  {
    planCode: "enterprise",
    name: "Enterprise",
    bestFor: "Best for larger schools",
    description: "Built for larger operations that need custom limits and priority-ready support.",
    priceMonthly: 80000,
    priceLabel: "From ₦80,000/mo",
    features: [
      "Advanced analytics",
      "AI assistant enabled",
      "Bulk import enabled",
      "Custom limits",
    ],
    limits: {
      students: null,
      teachers: null,
      parents: null,
      classes: null,
      subjects: null,
    },
    ctaLabel: "Choose Enterprise",
  },
];

const SUBSCRIPTION_SELECTION_STORAGE_KEY = "learnly_subscription_selection";

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
