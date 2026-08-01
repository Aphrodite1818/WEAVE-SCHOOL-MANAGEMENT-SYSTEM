export const TENANT_BRANDING_TOKEN_KEYS = Object.freeze([
  "--color-primary", "--color-primary-hover", "--color-primary-soft",
  "--color-primary-subtle", "--color-primary-deep", "--color-on-primary",
  "--color-accent", "--color-accent-hover", "--color-accent-soft", "--color-on-accent",
  "--color-background", "--color-surface", "--color-surface-raised",
  "--color-surface-muted", "--color-surface-subtle", "--color-border",
  "--color-border-strong", "--color-border-subtle", "--color-text",
  "--color-text-soft", "--color-text-muted", "--color-text-faint",
  "--color-text-inverse", "--color-sidebar-background", "--color-sidebar-text",
  "--color-sidebar-active", "--color-sidebar-active-text", "--color-sidebar-border",
  "--color-header-background", "--color-header-text", "--color-header-text-muted",
  "--color-header-surface", "--color-header-surface-hover", "--color-header-border",
  "--color-focus-ring",
]);

const TOKEN_KEY_SET = new Set(TENANT_BRANDING_TOKEN_KEYS);
const RGB_CHANNELS = /^(?:0|[1-9]\d?|1\d\d|2[0-4]\d|25[0-5]) (?:0|[1-9]\d?|1\d\d|2[0-4]\d|25[0-5]) (?:0|[1-9]\d?|1\d\d|2[0-4]\d|25[0-5])$/;

export const brandingCacheKey = (tenantId) => `weave-branding:${tenantId}`;

export function validateBrandingTokens(tokens) {
  if (!tokens || typeof tokens !== "object" || Array.isArray(tokens)) return null;
  const entries = Object.entries(tokens);
  if (entries.length !== TENANT_BRANDING_TOKEN_KEYS.length) return null;
  if (entries.some(([key, value]) => !TOKEN_KEY_SET.has(key) || !RGB_CHANNELS.test(String(value)))) return null;
  return Object.fromEntries(entries.map(([key, value]) => [key, String(value)]));
}

export function validateBrandingResponse(value, tenantId) {
  if (!value || String(value.tenant_id || "") !== String(tenantId || "")) return null;
  const lightTokens = validateBrandingTokens(value.light_tokens);
  const darkTokens = validateBrandingTokens(value.dark_tokens);
  if (!lightTokens || !darkTokens) return null;
  return { ...value, light_tokens: lightTokens, dark_tokens: darkTokens };
}

export function readCachedBranding(tenantId) {
  if (!tenantId) return null;
  for (const storage of [window.localStorage, window.sessionStorage]) {
    try {
      const value = validateBrandingResponse(JSON.parse(storage.getItem(brandingCacheKey(tenantId))), tenantId);
      if (value) return value;
    } catch { /* Ignore invalid or unavailable storage. */ }
  }
  return null;
}

export function writeCachedBranding(tenantId, value) {
  const validated = validateBrandingResponse(value, tenantId);
  if (!validated) return null;
  window.localStorage.setItem(brandingCacheKey(tenantId), JSON.stringify(validated));
  return validated;
}

export function clearAppliedBranding(element) {
  if (!element) return;
  TENANT_BRANDING_TOKEN_KEYS.forEach((key) => element.style.removeProperty(key));
  delete element.dataset.brandingTenantId;
  delete element.dataset.brandingVersion;
}

export function applyBranding(element, response, appearance) {
  clearAppliedBranding(element);
  if (!response?.is_enabled || response?.is_default_theme) return;
  const tokens = appearance === "dark" ? response.dark_tokens : response.light_tokens;
  const validated = validateBrandingTokens(tokens);
  if (!validated) return;
  Object.entries(validated).forEach(([key, value]) => element.style.setProperty(key, value));
  element.dataset.brandingTenantId = String(response.tenant_id);
  element.dataset.brandingVersion = String(response.theme_version || 0);
}
