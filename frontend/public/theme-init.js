(() => {
  try {
    const savedTheme = window.localStorage.getItem("theme");
    const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches;
    const resolvedTheme = ["light", "dark"].includes(savedTheme)
      ? savedTheme
      : prefersDark
        ? "dark"
        : "light";

    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.dataset.themePreference = ["light", "dark"].includes(savedTheme)
      ? savedTheme
      : "system";

    const tokenKeys = [
      "--color-primary", "--color-primary-hover", "--color-primary-soft", "--color-primary-subtle",
      "--color-primary-deep", "--color-on-primary", "--color-accent", "--color-accent-hover",
      "--color-accent-soft", "--color-on-accent", "--color-background", "--color-surface",
      "--color-surface-raised", "--color-surface-muted", "--color-surface-subtle", "--color-border",
      "--color-border-strong", "--color-border-subtle", "--color-text", "--color-text-soft",
      "--color-text-muted", "--color-text-faint", "--color-text-inverse", "--color-sidebar-background",
      "--color-sidebar-text", "--color-sidebar-active", "--color-sidebar-active-text",
      "--color-sidebar-border", "--color-header-background", "--color-header-text",
      "--color-header-text-muted", "--color-header-surface", "--color-header-surface-hover",
      "--color-header-border", "--color-focus-ring",
    ];
    const rgbChannels = /^(?:0|[1-9]\d?|1\d\d|2[0-4]\d|25[0-5]) (?:0|[1-9]\d?|1\d\d|2[0-4]\d|25[0-5]) (?:0|[1-9]\d?|1\d\d|2[0-4]\d|25[0-5])$/;
    const path = window.location.pathname;
    const tenantWorkspace = /^\/(admin|teacher|student|parent)(\/|$)/.test(path)
      && !/^\/(teacher|parent)\/schools(\/|$)/.test(path);
    const serializedUser = window.localStorage.getItem("auth_user") || window.sessionStorage.getItem("auth_user");
    const user = serializedUser ? JSON.parse(serializedUser) : null;
    const tenantId = user?.tenant_id || user?.tenant?.id;
    const actorType = String(user?.actor_type || user?.role || "").toLowerCase();
    if (tenantWorkspace && tenantId && !actorType.includes("superadmin")) {
      const serializedBranding = window.localStorage.getItem(`weave-branding:${tenantId}`)
        || window.sessionStorage.getItem(`weave-branding:${tenantId}`);
      const branding = serializedBranding ? JSON.parse(serializedBranding) : null;
      const tokens = resolvedTheme === "dark" ? branding?.dark_tokens : branding?.light_tokens;
      const valid = branding?.is_enabled === true
        && branding?.is_default_theme === false
        && branding?.token_schema_version === 2
        && String(branding?.tenant_id || "") === String(tenantId)
        && tokens && Object.keys(tokens).length === tokenKeys.length
        && tokenKeys.every((key) => rgbChannels.test(String(tokens[key] || "")));
      if (valid) {
        tokenKeys.forEach((key) => {
          if (key !== "--color-background") {
            document.documentElement.style.setProperty(key, tokens[key]);
          }
        });
        document.documentElement.dataset.startupTenantBranding = String(tenantId);
      }
    }

    const themeColor = resolvedTheme === "dark" ? "#0F172A" : "#FFFFFF";
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", themeColor);
  } catch {
    document.documentElement.dataset.theme = "light";
    document.documentElement.dataset.themePreference = "system";
  }
})();
