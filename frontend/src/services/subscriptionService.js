
import { API_BASE_URL, api } from "./api";

const PUBLIC_CATALOGUE_ETAG_KEY = "weave:public-pricing-etag";
const PUBLIC_CATALOGUE_VALUE_KEY = "weave:public-pricing-catalogue";

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
    const terms = await api.get("/tenant-admin/academics/terms?limit=100");
    const currentTerm = (terms?.items || terms || []).find((item) => item.is_current && item.status === "open");
    if (!currentTerm?.id) {
      throw new Error("Open an academic term before upgrading its plan.");
    }
    return subscriptionService.initializeTermCheckout({
      academic_term_id: currentTerm.id,
      plan_code: payload.plan_code,
    });
  },

  verifyTermPayment: (reference) =>
    api.get(`/subscriptions/terms/verify/${encodeURIComponent(reference)}`),
};

export default subscriptionService;
