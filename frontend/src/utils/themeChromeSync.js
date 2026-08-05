
const THEME_EVENT = "weave:accessibility-preferences-changed";
const STANDALONE_QUERY = "(display-mode: standalone)";
const LIGHT_THEME_COLOR = "#FFFFFF";
const DARK_THEME_COLOR = "#0F172A";
const BROWSER_THEME_RECHECK_DELAY_MS = 180;

let frameId = null;
let paintFrameId = null;
let timerId = null;

const resolvedTheme = () =>
  document.documentElement.dataset.theme === "dark" ? "dark" : "light";

const isStandalonePwa = () =>
  Boolean(
    window.matchMedia?.(STANDALONE_QUERY)?.matches ||
      window.navigator?.standalone === true,
  );

const fallbackColor = (theme) =>
  theme === "dark" ? DARK_THEME_COLOR : LIGHT_THEME_COLOR;

const resolveBackground = (theme) => {
  const channels = window
    .getComputedStyle(document.documentElement)
    .getPropertyValue("--color-background")
    .trim();
  return channels ? `rgb(${channels})` : fallbackColor(theme);
};

const replaceMeta = (name, attributes) => {
  document.querySelectorAll(`meta[name="${name}"]`).forEach((meta) => meta.remove());
  const meta = document.createElement("meta");
  meta.setAttribute("name", name);
  Object.entries(attributes).forEach(([key, value]) => meta.setAttribute(key, value));
  const anchor = document.head.querySelector(
    'meta[name="mobile-web-app-capable"], link[rel="manifest"], title',
  );
  document.head.insertBefore(meta, anchor || null);
  return meta;
};

const cancelScheduledSync = () => {
  if (frameId !== null) window.cancelAnimationFrame(frameId);
  if (paintFrameId !== null) window.cancelAnimationFrame(paintFrameId);
  if (timerId !== null) window.clearTimeout(timerId);
  frameId = null;
  paintFrameId = null;
  timerId = null;
};

const applyDocumentTheme = ({ replaceBrowserMetas = false } = {}) => {
  const theme = resolvedTheme();
  const background = resolveBackground(theme);
  const root = document.getElementById("root");

  document.documentElement.style.colorScheme = theme;
  document.documentElement.style.backgroundColor = background;
  if (document.body) {
    document.body.style.colorScheme = theme;
    document.body.style.backgroundColor = background;
  }
  if (root) {
    root.style.colorScheme = theme;
    root.style.backgroundColor = background;
  }

  // Declare both supported schemes. The active scheme remains authoritative
  // through the root CSS color-scheme property above.
  if (replaceBrowserMetas || !document.querySelector('meta[name="color-scheme"]')) {
    replaceMeta("color-scheme", { content: "light dark" });
  }

  if (replaceBrowserMetas || !document.querySelector('meta[name="theme-color"]')) {
    replaceMeta("theme-color", {
      content: background,
      "data-weave-theme": theme,
    });
  } else {
    const themeMeta = document.querySelector('meta[name="theme-color"]');
    themeMeta.removeAttribute("media");
    themeMeta.setAttribute("content", background);
    themeMeta.setAttribute("data-weave-theme", theme);
    document
      .querySelectorAll('meta[name="theme-color"]')
      .forEach((meta) => meta !== themeMeta && meta.remove());
  }
};

export const syncThemeChrome = () => {
  cancelScheduledSync();
  applyDocumentTheme({ replaceBrowserMetas: !isStandalonePwa() });

  if (isStandalonePwa()) return;

  frameId = window.requestAnimationFrame(() => {
    frameId = null;
    paintFrameId = window.requestAnimationFrame(() => {
      paintFrameId = null;
      applyDocumentTheme({ replaceBrowserMetas: true });
    });
  });

  timerId = window.setTimeout(() => {
    timerId = null;
    applyDocumentTheme({ replaceBrowserMetas: true });
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
    attributeFilter: ["data-theme", "data-theme-preference"],
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
    cancelScheduledSync();
    window.removeEventListener(THEME_EVENT, scheduleThemeChromeSync);
    window.removeEventListener("storage", scheduleThemeChromeSync);
    window.removeEventListener("pageshow", scheduleThemeChromeSync);
    window.removeEventListener("focus", scheduleThemeChromeSync);
    document.removeEventListener("visibilitychange", syncWhenVisible);
    colorSchemeQuery?.removeEventListener?.("change", scheduleThemeChromeSync);
  };
};
