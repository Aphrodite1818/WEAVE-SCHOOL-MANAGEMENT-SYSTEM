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

    const themeColor = resolvedTheme === "dark" ? "#0F172A" : "#FFFFFF";
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", themeColor);
  } catch {
    document.documentElement.dataset.theme = "light";
    document.documentElement.dataset.themePreference = "system";
  }
})();
