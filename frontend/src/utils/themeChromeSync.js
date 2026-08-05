const THEME_EVENT = "weave:accessibility-preferences-changed";
const STANDALONE_QUERY = "(display-mode: standalone)";
const LIGHT_THEME_COLOR = "#FFFFFF";
const DARK_THEME_COLOR = "#0F172A";
const BROWSER_THEME_RECHECK_DELAY_MS = 180;

let browserThemeFrameId = null;
let browserThemePaintFrameId = null;
let browserThemeTimerId = null;

const getResolvedTheme = () =>
  document.documentElement.dataset.theme === "dark" ? "dark" : "light";

const getFallbackThemeColor = (theme) =>
  theme === "dark" ? DARK_THEME_COLOR : LIGHT_THEME_COLOR;

const isStandalonePwa = () =>
  Boolean(
    window.matchMedia?.(STANDALONE_QUERY)?.matches ||
      window.navigator?.standalone === true,
  );

const resolveThemeBackground = (theme) => {
  const fallback = getFallbackThemeColor(theme);
  const channels = window
    .getComputedStyle(document.documentElement)
    .getPropertyValue("--color-background")
    .trim();

  return channels ? `rgb(${channels})` : fallback;
};

const ensureColorSchemeMeta = (theme) => {
  let meta = document.querySelector('meta[name="color-scheme"]');
  if (!meta) {
    meta = document.createElement("meta");
    meta.setAttribute("name", "color-scheme");
    document.head.appendChild(meta);
  }
  meta.setAttribute("content", theme);
};

const createThemeColorMeta = (theme, themeColor) => {
  const meta = document.createElement("meta");
  meta.setAttribute("name", "theme-color");
  meta.setAttribute("content", themeColor);
  meta.setAttribute("data-weave-theme", theme);
  return meta;
};

const themeColorAnchor = () =>
  document.head.querySelector(
    'meta[name="mobile-web-app-capable"], link[rel="manifest"], title',
  );

const removeDuplicateThemeColorMetas = (keep) => {
  document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
    if (meta !== keep) meta.remove();
  });
};

const updateSingleThemeColorMeta = (theme, themeColor) => {
  let meta = document.querySelector('meta[name="theme-color"]');
  if (!meta) {
    meta = createThemeColorMeta(theme, themeColor);
    document.head.insertBefore(meta, themeColorAnchor() || null);
  }

  removeDuplicateThemeColorMetas(meta);
  meta.removeAttribute("media");
  meta.removeAttribute("data-weave-browser-theme");
  meta.setAttribute("data-weave-theme", theme);
  meta.setAttribute("content", themeColor);
};

const replaceSingleThemeColorMeta = (theme, themeColor) => {
  document
    .querySelectorAll('meta[name="theme-color"]')
    .forEach((meta) => meta.remove());
  document.head.insertBefore(
    createThemeColorMeta(theme, themeColor),
    themeColorAnchor() || null,
  );
};

const cancelScheduledBrowserThemeSync = () => {
  if (browserThemeFrameId !== null) {
    window.cancelAnimationFrame(browserThemeFrameId);
    browserThemeFrameId = null;
  }
  if (browserThemePaintFrameId !== null) {
    window.cancelAnimationFrame(browserThemePaintFrameId);
    browserThemePaintFrameId = null;
  }
  if (browserThemeTimerId !== null) {
    window.clearTimeout(browserThemeTimerId);
    browserThemeTimerId = null;
  }
};

const writeThemeChrome = ({ replaceBrowserMeta = false } = {}) => {
  const theme = getResolvedTheme();
  const themeColor = resolveThemeBackground(theme);

  ensureColorSchemeMeta(theme);
  document.documentElement.style.colorScheme = theme;
  document.documentElement.style.backgroundColor = themeColor;

  if (document.body) {
    document.body.style.colorScheme = theme;
    document.body.style.backgroundColor = themeColor;
  }

  const root = document.getElementById("root");
  if (root) {
    root.style.colorScheme = theme;
    root.style.backgroundColor = themeColor;
  }

  if (replaceBrowserMeta && !isStandalonePwa()) {
    replaceSingleThemeColorMeta(theme, themeColor);
  } else {
    updateSingleThemeColorMeta(theme, themeColor);
  }
};

export const syncThemeChrome = () => {
  cancelScheduledBrowserThemeSync();
  writeThemeChrome();

  if (isStandalonePwa()) return;

  // Theme attributes update before tenant branding tokens and React effects have
  // necessarily painted. The second frame is the authoritative browser write.
  browserThemeFrameId = window.requestAnimationFrame(() => {
    browserThemeFrameId = null;
    browserThemePaintFrameId = window.requestAnimationFrame(() => {
      browserThemePaintFrameId = null;
      writeThemeChrome({ replaceBrowserMeta: true });
    });
  });

  // Mobile browsers occasionally defer theme-color adoption. Reassert the same
  // resolved value after the paint without requiring a page refresh.
  browserThemeTimerId = window.setTimeout(() => {
    browserThemeTimerId = null;
    writeThemeChrome();
  }, BROWSER_THEME_RECHECK_DELAY_MS);
};

export const scheduleThemeChromeSync = () => {
  if (typeof window === "undefined" || typeof document === "undefined") return;
  syncThemeChrome();
};

export const installThemeChromeSync = () => {
  syncThemeChrome();

  const observer = new MutationObserver(scheduleThemeChromeSync);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });

  const colorSchemeQuery = window.matchMedia?.("(prefers-color-scheme: dark)");
  const syncWhenVisible = () => {
    if (!document.hidden) scheduleThemeChromeSync();
  };

  window.addEventListener(THEME_EVENT, scheduleThemeChromeSync);
  window.addEventListener("storage", scheduleThemeChromeSync);
  window.addEventListener("pageshow", scheduleThemeChromeSync);
  window.addEventListener("focus", scheduleThemeChromeSync);
  document.addEventListener("visibilitychange", syncWhenVisible);
  colorSchemeQuery?.addEventListener?.("change", scheduleThemeChromeSync);

  return () => {
    observer.disconnect();
    cancelScheduledBrowserThemeSync();
    window.removeEventListener(THEME_EVENT, scheduleThemeChromeSync);
    window.removeEventListener("storage", scheduleThemeChromeSync);
    window.removeEventListener("pageshow", scheduleThemeChromeSync);
    window.removeEventListener("focus", scheduleThemeChromeSync);
    document.removeEventListener("visibilitychange", syncWhenVisible);
    colorSchemeQuery?.removeEventListener?.("change", scheduleThemeChromeSync);
  };
};
