const THEME_EVENT = "weave:accessibility-preferences-changed";
const STANDALONE_QUERY = "(display-mode: standalone)";
const LIGHT_THEME_COLOR = "#FFFFFF";
const DARK_THEME_COLOR = "#0F172A";
const BROWSER_THEME_RECHECK_DELAY_MS = 160;

let browserThemeFrameId = null;
let browserThemeTimerId = null;

const getResolvedTheme = () =>
  document.documentElement.dataset.theme === "dark" ? "dark" : "light";

const getThemeColor = (theme) =>
  theme === "dark" ? DARK_THEME_COLOR : LIGHT_THEME_COLOR;

const isStandalonePwa = () =>
  Boolean(
    window.matchMedia?.(STANDALONE_QUERY)?.matches ||
      window.navigator?.standalone === true,
  );

const ensureColorSchemeMeta = (theme) => {
  let meta = document.querySelector('meta[name="color-scheme"]');
  if (!meta) {
    meta = document.createElement("meta");
    meta.setAttribute("name", "color-scheme");
    document.head.appendChild(meta);
  }
  meta.setAttribute("content", theme);
};

const createThemeColorMeta = (theme) => {
  const meta = document.createElement("meta");
  meta.setAttribute("name", "theme-color");
  meta.setAttribute("content", getThemeColor(theme));
  meta.setAttribute("data-weave-theme", theme);
  return meta;
};

const themeColorAnchor = () =>
  document.head.querySelector(
    'meta[name="mobile-web-app-capable"], link[rel="manifest"], title',
  );

const removeDuplicateThemeColorMetas = (keep) => {
  document
    .querySelectorAll('meta[name="theme-color"]')
    .forEach((meta) => {
      if (meta !== keep) meta.remove();
    });
};

const updateSingleThemeColorMeta = (theme) => {
  let meta = document.querySelector('meta[name="theme-color"]');
  if (!meta) {
    meta = createThemeColorMeta(theme);
    document.head.insertBefore(meta, themeColorAnchor() || null);
  }

  removeDuplicateThemeColorMetas(meta);
  meta.removeAttribute("media");
  meta.removeAttribute("data-weave-browser-theme");
  meta.setAttribute("data-weave-theme", theme);
  meta.setAttribute("content", getThemeColor(theme));
};

const replaceSingleThemeColorMeta = (theme) => {
  document
    .querySelectorAll('meta[name="theme-color"]')
    .forEach((meta) => meta.remove());
  document.head.insertBefore(
    createThemeColorMeta(theme),
    themeColorAnchor() || null,
  );
};

const cancelScheduledBrowserThemeSync = () => {
  if (browserThemeFrameId !== null) {
    window.cancelAnimationFrame(browserThemeFrameId);
    browserThemeFrameId = null;
  }
  if (browserThemeTimerId !== null) {
    window.clearTimeout(browserThemeTimerId);
    browserThemeTimerId = null;
  }
};

const writeStandaloneThemeColor = (theme) => {
  updateSingleThemeColorMeta(theme);
};

const writeBrowserThemeColor = (theme, { replace = false } = {}) => {
  ensureColorSchemeMeta(theme);
  if (replace) {
    replaceSingleThemeColorMeta(theme);
    return;
  }
  updateSingleThemeColorMeta(theme);
};

const syncThemeColor = (theme) => {
  if (isStandalonePwa()) {
    cancelScheduledBrowserThemeSync();
    writeStandaloneThemeColor(theme);
    return;
  }

  cancelScheduledBrowserThemeSync();
  writeBrowserThemeColor(theme);

  browserThemeFrameId = window.requestAnimationFrame(() => {
    writeBrowserThemeColor(theme, { replace: true });
    browserThemeFrameId = null;
  });

  browserThemeTimerId = window.setTimeout(() => {
    writeBrowserThemeColor(theme);
    browserThemeTimerId = null;
  }, BROWSER_THEME_RECHECK_DELAY_MS);
};

export const syncThemeChrome = () => {
  const theme = getResolvedTheme();
  const themeColor = getThemeColor(theme);
  const background = "rgb(var(--color-background))";

  ensureColorSchemeMeta(theme);
  document.documentElement.style.colorScheme = theme;
  document.documentElement.style.backgroundColor = themeColor;

  if (document.body) {
    document.body.style.colorScheme = theme;
    document.body.style.backgroundColor = background;
  }

  const root = document.getElementById("root");
  if (root) {
    root.style.colorScheme = theme;
    root.style.backgroundColor = background;
  }

  syncThemeColor(theme);
};

export const installThemeChromeSync = () => {
  syncThemeChrome();

  const observer = new MutationObserver(syncThemeChrome);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });

  const colorSchemeQuery = window.matchMedia?.("(prefers-color-scheme: dark)");
  const syncWhenVisible = () => {
    if (!document.hidden) syncThemeChrome();
  };

  window.addEventListener(THEME_EVENT, syncThemeChrome);
  window.addEventListener("storage", syncThemeChrome);
  window.addEventListener("pageshow", syncThemeChrome);
  window.addEventListener("focus", syncThemeChrome);
  document.addEventListener("visibilitychange", syncWhenVisible);
  colorSchemeQuery?.addEventListener?.("change", syncThemeChrome);

  return () => {
    observer.disconnect();
    cancelScheduledBrowserThemeSync();
    window.removeEventListener(THEME_EVENT, syncThemeChrome);
    window.removeEventListener("storage", syncThemeChrome);
    window.removeEventListener("pageshow", syncThemeChrome);
    window.removeEventListener("focus", syncThemeChrome);
    document.removeEventListener("visibilitychange", syncWhenVisible);
    colorSchemeQuery?.removeEventListener?.("change", syncThemeChrome);
  };
};
