import { API_BASE_URL, api } from "./api";

const PUBLIC_CATALOGUE_ETAG_KEY = "weave:public-pricing-etag";
const PUBLIC_CATALOGUE_VALUE_KEY = "weave:public-pricing-catalogue";
const TERM_PAYMENT_OPEN_INTENT_KEY = "weave:term-payment-open-intent";
const TERM_ORDER = {
  first_term: 1,
  second_term: 2,
  third_term: 3,
};

const backgroundAuthOptions = {
  clearAuthOnUnauthorized: false,
};

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
    return JSON.parse(window.sessionStorage.getItem(PUBLIC_CATALOGUE_VALUE_KEY) || "null");
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
    const error = new Error(data?.detail || data?.message || "Pricing catalogue unavailable.");
    error.response = { status: response.status, data };
    throw error;
  }

  const etag = response.headers.get("etag");
  if (etag) window.sessionStorage.setItem(PUBLIC_CATALOGUE_ETAG_KEY, etag);
  window.sessionStorage.setItem(PUBLIC_CATALOGUE_VALUE_KEY, JSON.stringify(data));
  return data;
};

const resolveCheckoutTermId = async (explicitTermId) => {
  if (explicitTermId) return explicitTermId;

  const [termsResponse, sessionsResponse] = await Promise.all([
    api.get("/tenant-admin/academics/terms?limit=100"),
    api.get("/tenant-admin/academics/sessions?limit=100&status=open&is_current=true"),
  ]);
  const terms = termsResponse?.items || termsResponse || [];
  const sessions = sessionsResponse?.items || sessionsResponse || [];

  const currentTerm = terms.find(
    (item) => item.is_current && item.status === "open",
  );
  if (currentTerm?.id) return currentTerm.id;

  const currentSession = sessions.find(
    (item) => item.is_current && item.status === "open",
  );
  const draftTerms = terms
    .filter(
      (item) =>
        item.status === "draft" &&
        (!currentSession?.id || item.academic_session_id === currentSession.id),
    )
    .sort((left, right) => {
      const orderDifference =
        (TERM_ORDER[left.name] ?? 99) - (TERM_ORDER[right.name] ?? 99);
      if (orderDifference !== 0) return orderDifference;
      return String(left.start_date || "").localeCompare(String(right.start_date || ""));
    });

  if (draftTerms[0]?.id) return draftTerms[0].id;
  throw new Error("Create a draft academic term before purchasing a term plan.");
};

const saveTermPaymentOpenIntent = ({ academicTermId, reference } = {}) => {
  if (typeof window === "undefined" || !academicTermId || !reference) return;
  window.sessionStorage.setItem(
    TERM_PAYMENT_OPEN_INTENT_KEY,
    JSON.stringify({
      academicTermId: String(academicTermId),
      reference: String(reference),
    }),
  );
};

const consumeTermPaymentOpenIntent = ({ academicTermId, reference } = {}) => {
  if (typeof window === "undefined") return null;

  try {
    const rawValue = window.sessionStorage.getItem(TERM_PAYMENT_OPEN_INTENT_KEY);
    if (!rawValue) return null;

    const intent = JSON.parse(rawValue);
    const sameTerm = String(intent?.academicTermId || "") === String(academicTermId || "");
    const sameReference = String(intent?.reference || "") === String(reference || "");
    if (!sameTerm || !sameReference) return null;

    window.sessionStorage.removeItem(TERM_PAYMENT_OPEN_INTENT_KEY);
    return intent;
  } catch {
    window.sessionStorage.removeItem(TERM_PAYMENT_OPEN_INTENT_KEY);
    return null;
  }
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
    api.get(`/subscriptions/payments${queryString(params)}`, backgroundAuthOptions),

  getTermPlanHistory: () =>
    api.get("/subscriptions/terms/history", backgroundAuthOptions),

  activateFreeTerm: (academicTermId) =>
    api.post("/subscriptions/terms/activate-free", {
      academic_term_id: academicTermId,
      confirmation: "ACTIVATE_FREE_TERM",
    }),

  initializeTermCheckout: async (payload) => {
    await getPublicPlans({ force: true });
    return api.post("/subscriptions/terms/checkout", payload);
  },

  initializePaidCurrentTermCheckout: async (payload) => {
    const academicTermId = await resolveCheckoutTermId(
      payload.academic_term_id || payload.academicTermId,
    );
    return subscriptionService.initializeTermCheckout({
      academic_term_id: academicTermId,
      plan_code: payload.plan_code,
    });
  },

  verifyTermPayment: (reference) =>
    api.get(`/subscriptions/terms/verify/${encodeURIComponent(reference)}`),

  saveTermPaymentOpenIntent,

  consumeTermPaymentOpenIntent,
};

export default subscriptionService;
