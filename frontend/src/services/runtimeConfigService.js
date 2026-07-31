import { api } from "./api";

const DEFAULT_CONFIG = {
  environment: "dev",
  production_like: false,
  features: {
    attendance: false,
    messaging: false,
    announcements: true,
    inbox: true,
  },
};

const CONFIG_CHANGED_EVENT = "weave:runtime-config-changed";
let cachedConfig = DEFAULT_CONFIG;
let loadPromise = null;

export const getRuntimeConfigSnapshot = () => cachedConfig;

export const runtimeFeatureEnabled = (featureCode) =>
  cachedConfig?.features?.[featureCode] !== false;

export const loadRuntimeConfig = async () => {
  if (!loadPromise) {
    loadPromise = api
      .get("/runtime-config", { auth: false, clearAuthOnUnauthorized: false })
      .then((response) => {
        cachedConfig = {
          ...DEFAULT_CONFIG,
          ...(response || {}),
          features: {
            ...DEFAULT_CONFIG.features,
            ...(response?.features || {}),
          },
        };
        window.dispatchEvent(new CustomEvent(CONFIG_CHANGED_EVENT));
        return cachedConfig;
      })
      .catch(() => cachedConfig)
      .finally(() => {
        loadPromise = null;
      });
  }
  return loadPromise;
};

export const subscribeRuntimeConfig = (listener) => {
  window.addEventListener(CONFIG_CHANGED_EVENT, listener);
  return () => window.removeEventListener(CONFIG_CHANGED_EVENT, listener);
};
