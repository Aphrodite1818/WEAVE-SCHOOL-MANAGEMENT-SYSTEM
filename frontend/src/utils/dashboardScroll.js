export function scrollDashboardViewportToTop(behavior = "smooth") {
  if (typeof window === "undefined") return;

  const dashboardContent = document.getElementById("dashboard-content");
  const scrollingElement =
    document.scrollingElement || document.documentElement || document.body;

  if (dashboardContent && typeof dashboardContent.scrollTo === "function") {
    dashboardContent.scrollTo({ top: 0, behavior });
  }

  if (scrollingElement && typeof scrollingElement.scrollTo === "function") {
    scrollingElement.scrollTo({ top: 0, behavior });
  } else if (scrollingElement) {
    scrollingElement.scrollTop = 0;
  }

  if (typeof window.scrollTo === "function") {
    window.scrollTo({ top: 0, behavior });
  }
}
