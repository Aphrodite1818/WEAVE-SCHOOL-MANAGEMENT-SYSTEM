const THEME_EVENT = "weave:accessibility-preferences-changed";

const getResolvedTheme = () =>
  document.documentElement.dataset.theme === "dark" ? "dark" : "light";

const ensureColorSchemeMeta = () => {
  let meta = document.querySelector('meta[name="color-scheme"]');
  if (!meta) {
    meta = document.createElement("meta");
    meta.setAttribute("name", "color-scheme");
    document.head.appendChild(meta);
  }
  meta.setAttribute("content", "light dark");
};

export const syncThemeChrome = () => {
  const theme = getResolvedTheme();
  const themeColor = theme === "dark" ? "#0F172A" : "#FFFFFF";
  const background = "rgb(var(--color-background))";

  ensureColorSchemeMeta();
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
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", themeColor);
};

export const installThemeChromeSync = () => {
  syncThemeChrome();

  const observer = new MutationObserver(syncThemeChrome);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });

  window.addEventListener(THEME_EVENT, syncThemeChrome);
  window.addEventListener("storage", syncThemeChrome);
  window
    .matchMedia?.("(prefers-color-scheme: dark)")
    ?.addEventListener?.("change", syncThemeChrome);

  return () => {
    observer.disconnect();
    window.removeEventListener(THEME_EVENT, syncThemeChrome);
    window.removeEventListener("storage", syncThemeChrome);
  };
};
