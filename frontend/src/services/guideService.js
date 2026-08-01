import { api, authSession } from "./api";

const storageKey = (guideKey) => {
  const user = authSession.getUser() || {};
  const actor = user.id || user.email || "anonymous";
  const tenant = user.tenant_id || user.membership_id || "global";
  return `weave:guide:${tenant}:${actor}:${guideKey}`;
};

const fallbackState = (guideKey) => {
  try {
    const raw = window.localStorage.getItem(storageKey(guideKey));
    if (raw) return JSON.parse(raw);
  } catch {
    // Local persistence is only a resilience fallback.
  }
  return {
    guide_key: guideKey,
    status: "not_started",
    current_step: null,
    skipped_steps: [],
    remind_after: null,
  };
};

const persistFallback = (guideKey, state) => {
  try {
    window.localStorage.setItem(storageKey(guideKey), JSON.stringify(state));
  } catch {
    // A blocked storage API must not break the dashboard.
  }
};

export const guideService = {
  async getState(guideKey) {
    try {
      const response = await api.get(`/guides/${guideKey}`, {
        clearAuthOnUnauthorized: false,
      });
      persistFallback(guideKey, response);
      return response;
    } catch {
      return fallbackState(guideKey);
    }
  },

  async updateState(guideKey, payload) {
    const optimistic = {
      ...fallbackState(guideKey),
      ...payload,
      guide_key: guideKey,
      updated_at: new Date().toISOString(),
    };
    persistFallback(guideKey, optimistic);
    try {
      const response = await api.patch(`/guides/${guideKey}`, payload, {
        clearAuthOnUnauthorized: false,
      });
      persistFallback(guideKey, response);
      return response;
    } catch {
      return optimistic;
    }
  },
};
