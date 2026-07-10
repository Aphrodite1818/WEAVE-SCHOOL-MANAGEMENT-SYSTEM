export const TENANT_BRANDING_UPDATED_EVENT = "learnly:tenant-brand-updated";

export const DEFAULT_TENANT_THEME_TOKENS = {
  "--color-primary": "37 99 235",
  "--color-primary-hover": "29 78 216",
  "--color-primary-soft": "219 234 254",
  "--color-primary-subtle": "239 246 255",
  "--color-primary-deep": "30 58 138",
  "--color-accent": "79 70 229",
  "--color-accent-hover": "67 56 202",
  "--color-accent-soft": "224 231 255",
  "--color-workspace-background": "248 250 252",
  "--color-header-background": "248 250 252",
  "--color-header-text": "15 23 42",
  "--color-header-text-muted": "100 116 139",
  "--color-header-surface": "255 255 255",
  "--color-header-surface-hover": "241 245 249",
  "--color-header-border": "226 232 240",
  "--color-sidebar-background": "15 23 42",
  "--color-sidebar-text": "255 255 255",
};

export const DEFAULT_TENANT_BRANDING = {
  brand_name: "Learnly AI",
  primary_color: "#2563EB",
  accent_color: "#4F46E5",
  sidebar_color: "#0F172A",
  header_color: "#F8FAFC",
  background_color: "#F8FAFC",
  theme_mode: "light",
  is_enabled: false,
  theme_version: 0,
  is_default_theme: true,
  tokens: DEFAULT_TENANT_THEME_TOKENS,
};

export function normalizeTenantBrandingTokens(tokens = {}) {
  return {
    ...DEFAULT_TENANT_THEME_TOKENS,
    ...(tokens || {}),
  };
}

export function applyTenantBranding(branding = DEFAULT_TENANT_BRANDING) {
  if (typeof document === "undefined") return;

  const root = document.documentElement;
  const tokens = normalizeTenantBrandingTokens(branding?.tokens);

  Object.entries(tokens).forEach(([tokenName, tokenValue]) => {
    root.style.setProperty(tokenName, tokenValue);
  });
}

export function resetTenantBranding() {
  applyTenantBranding(DEFAULT_TENANT_BRANDING);
}

export function emitTenantBrandingUpdated(detail = {}) {
  if (typeof window === "undefined") return;

  window.dispatchEvent(
    new CustomEvent(TENANT_BRANDING_UPDATED_EVENT, {
      detail,
    })
  );
}
