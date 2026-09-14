import { api, authSession } from "./api";

const TERMINAL_STATUSES = new Set(["completed", "dismissed"]);
const ACCOUNT_SCOPED_ACTOR_TYPES = new Set([
  "teacher",
  "teacher_account",
  "teacher_membership",
  "parent",
  "parent_account",
  "parent_membership",
]);
const PENDING_SUFFIX = ":pending";
const inFlightReads = new Map();

const storageKey = (guideKey) => {
  const user = authSession.getUser() || {};
  const actorType = String(
    user.actor_type || user.account_type || user.role || "",
  ).toLowerCase();
  const accountScoped = ACCOUNT_SCOPED_ACTOR_TYPES.has(actorType);
  const actor =
    user.account_id ||
    user.teacher_account_id ||
    user.parent_account_id ||
    user.meta?.teacher_account_id ||
    user.meta?.parent_account_id ||
    user.actor_id ||
    user.id ||
    user.email ||
    user.admission_number ||
    "anonymous";
  const tenant = accountScoped
    ? "global"
    : user.tenant_id || user.tenant?.id || user.membership_id || "global";
  return `weave:guide:${tenant}:${actor}:${guideKey}`;
};

const readJson = (key) => {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const writeJson = (key, value) => {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // A blocked storage API must not break the dashboard.
  }
};

const removeStoredValue = (key) => {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // A blocked storage API must not break the dashboard.
  }
};

const emptyState = (guideKey) => ({
  guide_key: guideKey,
  status: "not_started",
  current_step: null,
  skipped_steps: [],
  remind_after: null,
  sync_pending: false,
});

const normalizeState = (guideKey, value, { syncPending = false } = {}) => ({
  ...emptyState(guideKey),
  ...(value || {}),
  guide_key: guideKey,
  skipped_steps: Array.isArray(value?.skipped_steps) ? value.skipped_steps : [],
  sync_pending: syncPending || Boolean(value?.sync_pending),
});

const fallbackState = (guideKey) =>
  normalizeState(guideKey, readJson(storageKey(guideKey)));

const persistFallback = (guideKey, state) => {
  const normalized = normalizeState(guideKey, state, {
    syncPending: Boolean(state?.sync_pending),
  });
  writeJson(storageKey(guideKey), normalized);
  return normalized;
};

const pendingKey = (guideKey) => `${storageKey(guideKey)}${PENDING_SUFFIX}`;

const readPending = (guideKey) => readJson(pendingKey(guideKey));

const persistPending = (guideKey, payload) => {
  writeJson(pendingKey(guideKey), {
    payload,
    queued_at: new Date().toISOString(),
  });
};

const clearPending = (guideKey) => removeStoredValue(pendingKey(guideKey));

const isTerminal = (state) => TERMINAL_STATUSES.has(state?.status);

const terminalPayload = (state) => ({
  status: state.status,
  current_step: state.current_step || null,
  skipped_steps: Array.isArray(state.skipped_steps) ? state.skipped_steps : [],
  remind_after: null,
});

const ensureTerminalConfirmation = (requestedStatus, state) => {
  if (!TERMINAL_STATUSES.has(requestedStatus)) return state;

  const confirmed =
    requestedStatus === "completed"
      ? state?.status === "completed"
      : TERMINAL_STATUSES.has(state?.status);
  if (!confirmed) {
    throw new Error("Guide completion was not confirmed by the server.");
  }
  return state;
};

const shouldPreserveLocalState = (localState, serverState) => {
  if (localState?.sync_pending) return true;
  if (isTerminal(localState) && !isTerminal(serverState)) return true;
  if (
    localState?.status === "completed" &&
    serverState?.status === "dismissed"
  ) {
    return true;
  }
  return false;
};

const confirmPendingState = async (guideKey, localState, pending) => {
  const payload =
    pending?.payload ||
    (isTerminal(localState) ? terminalPayload(localState) : null);
  if (!payload) return null;

  const response = await api.patch(`/guides/${guideKey}`, payload, {
    clearAuthOnUnauthorized: false,
  });
  ensureTerminalConfirmation(payload?.status, response);
  clearPending(guideKey);
  return persistFallback(
    guideKey,
    normalizeState(guideKey, response, { syncPending: false }),
  );
};

const getStateOnce = async (guideKey) => {
  const localState = fallbackState(guideKey);
  const pending = readPending(guideKey);

  try {
    const response = await api.get(`/guides/${guideKey}`, {
      clearAuthOnUnauthorized: false,
    });
    const serverState = normalizeState(guideKey, response);

    if (pending || shouldPreserveLocalState(localState, serverState)) {
      const pendingLocalState = persistFallback(guideKey, {
        ...localState,
        sync_pending: true,
      });
      try {
        return await confirmPendingState(guideKey, pendingLocalState, pending);
      } catch {
        return pendingLocalState;
      }
    }

    clearPending(guideKey);
    return persistFallback(guideKey, {
      ...serverState,
      sync_pending: false,
    });
  } catch {
    return persistFallback(guideKey, {
      ...localState,
      sync_pending: true,
    });
  }
};

export const guideService = {
  async getState(guideKey) {
    const key = storageKey(guideKey);
    if (inFlightReads.has(key)) return inFlightReads.get(key);

    const request = getStateOnce(guideKey).finally(() => {
      if (inFlightReads.get(key) === request) inFlightReads.delete(key);
    });
    inFlightReads.set(key, request);
    return request;
  },

  async updateState(guideKey, payload) {
    const currentState = fallbackState(guideKey);
    const requestedStatus = payload?.status;
    const terminalWrite = TERMINAL_STATUSES.has(requestedStatus);
    const preserveCompleted =
      currentState.status === "completed" && requestedStatus !== "completed";
    const preserveDismissed =
      currentState.status === "dismissed" &&
      !TERMINAL_STATUSES.has(requestedStatus);
    if (preserveCompleted || preserveDismissed) return currentState;

    persistPending(guideKey, payload);

    if (terminalWrite) {
      try {
        const response = await api.patch(`/guides/${guideKey}`, payload, {
          clearAuthOnUnauthorized: false,
        });
        ensureTerminalConfirmation(requestedStatus, response);
        clearPending(guideKey);
        return persistFallback(guideKey, {
          ...response,
          sync_pending: false,
        });
      } catch (error) {
        persistFallback(guideKey, {
          ...currentState,
          sync_pending: true,
        });
        throw error;
      }
    }

    const optimistic = persistFallback(guideKey, {
      ...currentState,
      ...payload,
      guide_key: guideKey,
      updated_at: new Date().toISOString(),
      sync_pending: true,
    });

    try {
      const response = await api.patch(`/guides/${guideKey}`, payload, {
        clearAuthOnUnauthorized: false,
      });
      clearPending(guideKey);
      return persistFallback(guideKey, {
        ...response,
        sync_pending: false,
      });
    } catch {
      return optimistic;
    }
  },

  async retryPendingState(guideKey) {
    const localState = fallbackState(guideKey);
    const pending = readPending(guideKey);
    if (!pending && !localState.sync_pending) return localState;
    if (!pending) return getStateOnce(guideKey);

    try {
      return await confirmPendingState(guideKey, localState, pending);
    } catch {
      return persistFallback(guideKey, {
        ...localState,
        sync_pending: true,
      });
    }
  },
};
