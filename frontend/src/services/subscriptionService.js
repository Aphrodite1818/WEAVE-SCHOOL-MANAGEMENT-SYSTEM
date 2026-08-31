import { API_BASE_URL, api } from "./api";

const PUBLIC_CATALOGUE_ETAG_KEY = "weave:public-pricing-etag";
const PUBLIC_CATALOGUE_VALUE_KEY = "weave:public-pricing-catalogue";
const TERM_PAYMENT_INTENT_KEY = "weave:term-payment-intent";
const backgroundAuthOptions = {
  clearAuthOnUnauthorized: false,
};

const SAFE_RETURN_PREFIXES = [
  "/admin/getting-started",
  "/admin/academic/terms",
  "/admin/billing",
  "/admin/students",
  "/admin/teachers",
  "/admin/parents",
];

const queryString = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const value = query.toString();
  return value ? `?${value}` : "";
};

const readStoredCatalogue = () => {
  try {
    return JSON.parse(
      window.sessionStorage.getItem(PUBLIC_CATALOGUE_VALUE_KEY) || "null",
    );
  } catch {
    window.sessionStorage.removeItem(PUBLIC_CATALOGUE_VALUE_KEY);
    return null;
  }
};

const getPublicPlans = async ({ force = false } = {}) => {
  const storedEtag = window.sessionStorage.getItem(PUBLIC_CATALOGUE_ETAG_KEY);
  const headers = {};
  if (!force && storedEtag) headers["If-None-Match"] = storedEtag;

  const response = await fetch(`${API_BASE_URL}/subscriptions/plans`, {
    method: "GET",
    credentials: "include",
    cache: "no-cache",
    headers,
  });

  if (response.status === 304) {
    const cached = readStoredCatalogue();
    if (cached) return cached;
    return getPublicPlans({ force: true });
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      data?.detail || data?.message || "Pricing catalogue unavailable.",
    );
    error.response = { status: response.status, data };
    throw error;
  }

  const etag = response.headers.get("etag");
  if (etag) window.sessionStorage.setItem(PUBLIC_CATALOGUE_ETAG_KEY, etag);
  window.sessionStorage.setItem(
    PUBLIC_CATALOGUE_VALUE_KEY,
    JSON.stringify(data),
  );
  return data;
};

const resolveCurrentOpenTermId = async (explicitTermId) => {
  if (explicitTermId) return explicitTermId;

  const termsResponse = await api.get("/tenant-admin/academics/terms?limit=100");
  const terms = termsResponse?.items || termsResponse || [];
  const currentTerms = terms.filter(
    (item) => item.is_current && item.status === "open",
  );

  if (currentTerms.length === 1 && currentTerms[0]?.id) {
    return currentTerms[0].id;
  }
  if (currentTerms.length > 1) {
    throw new Error(
      "Academic term state is inconsistent. Resolve the current term before managing a plan.",
    );
  }
  throw new Error(
    "There is no open academic term to manage. Choose a plan when opening the next term.",
  );
};

const safeReturnPath = (value, fallback = "/admin/billing") => {
  const path = String(value || "").trim();
  if (!path.startsWith("/")) return fallback;
  return SAFE_RETURN_PREFIXES.some(
    (prefix) =>
      path === prefix ||
      path.startsWith(`${prefix}/`) ||
      path.startsWith(`${prefix}?`),
  )
    ? path
    : fallback;
};

const saveTermPaymentIntent = ({
  academicTermId,
  reference,
  origin = "billing",
  returnPath = "/admin/billing",
  postPaymentAction = "none",
} = {}) => {
  if (typeof window === "undefined" || !academicTermId || !reference) return;

  window.sessionStorage.setItem(
    TERM_PAYMENT_INTENT_KEY,
    JSON.stringify({
      academicTermId: String(academicTermId),
      reference: String(reference),
      origin: String(origin || "billing"),
      returnPath: safeReturnPath(returnPath),
      postPaymentAction:
        postPaymentAction === "open_term" ? "open_term" : "none",
    }),
  );
};

const consumeTermPaymentIntent = ({ academicTermId, reference } = {}) => {
  if (typeof window === "undefined") return null;

  try {
    const rawValue = window.sessionStorage.getItem(TERM_PAYMENT_INTENT_KEY);
    if (!rawValue) return null;

    const intent = JSON.parse(rawValue);
    const sameTerm =
      String(intent?.academicTermId || "") === String(academicTermId || "");
    const sameReference =
      String(intent?.reference || "") === String(reference || "");
    if (!sameTerm || !sameReference) return null;

    window.sessionStorage.removeItem(TERM_PAYMENT_INTENT_KEY);
    return {
      ...intent,
      returnPath: safeReturnPath(intent?.returnPath),
      postPaymentAction:
        intent?.postPaymentAction === "open_term" ? "open_term" : "none",
    };
  } catch {
    window.sessionStorage.removeItem(TERM_PAYMENT_INTENT_KEY);
    return null;
  }
};

const checkoutRedirectUrl = (checkout = {}) => {
  const value = String(checkout.authorization_url || "").trim();
  if (!value) {
    throw new Error(
      "Paystack did not return a checkout link. Please try again.",
    );
  }
  return value;
};

export const subscriptionService = {
  getPublicPlans,

  getCurrentSubscription: () =>
    api.get("/subscriptions/current", backgroundAuthOptions),

  getSubscriptionEntitlements: () =>
    api.get("/subscriptions/entitlements", backgroundAuthOptions),

  getActorEntitlements: () =>
    api.get("/subscriptions/actor-entitlements", backgroundAuthOptions),

  getPaymentHistory: (params = {}) =>
    api.get(
      `/subscriptions/payments${queryString(params)}`,
      backgroundAuthOptions,
    ),

  getTermPlanHistory: () =>
    api.get("/subscriptions/terms/history", backgroundAuthOptions),

  getTermPlanOptions: (academicTermId) =>
    api.get(
      `/subscriptions/terms/${encodeURIComponent(academicTermId)}/plan-options`,
      backgroundAuthOptions,
    ),

  activateFreeTerm: (academicTermId) =>
    api.post("/subscriptions/terms/activate-free", {
      academic_term_id: academicTermId,
      confirmation: "ACTIVATE_FREE_TERM",
    }),

  changeTermPlan: ({ academicTermId, targetPlan }) =>
    api.post("/subscriptions/terms/change-plan", {
      academic_term_id: academicTermId,
      target_plan: targetPlan,
      confirmation: "CHANGE_TERM_PLAN",
    }),

  initializeTermCheckout: async (payload) => {
    await getPublicPlans({ force: true });
    if (!payload?.academic_term_id) {
      throw new Error("Academic term is required before starting checkout.");
    }
    return api.post("/subscriptions/terms/checkout", payload);
  },

  initializePaidCurrentTermCheckout: async (payload) => {
    const academicTermId = await resolveCurrentOpenTermId(
      payload.academic_term_id || payload.academicTermId,
    );
    return subscriptionService.initializeTermCheckout({
      academic_term_id: academicTermId,
      plan_code: payload.plan_code,
    });
  },

  verifyTermPayment: (reference) =>
    api.get(`/subscriptions/terms/verify/${encodeURIComponent(reference)}`),

  checkoutRedirectUrl,
  safeReturnPath,
  saveTermPaymentIntent,
  consumeTermPaymentIntent,

  saveTermPaymentOpenIntent: ({ academicTermId, reference } = {}) =>
    saveTermPaymentIntent({
      academicTermId,
      reference,
      origin: "academic-terms",
      returnPath: "/admin/academic/terms",
      postPaymentAction: "open_term",
    }),

  consumeTermPaymentOpenIntent: ({ academicTermId, reference } = {}) => {
    const intent = consumeTermPaymentIntent({ academicTermId, reference });
    return intent?.postPaymentAction === "open_term" ? intent : null;
  },
};

export default subscriptionService;
