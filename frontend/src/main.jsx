import { createRoot } from 'react-dom/client'
import './index.css'
import './styles/mobileDashboard.css'
import './styles/mobileOverrides.css'
import './styles/pwaInteractions.css'
import './styles/brandAssets.css'
import './styles/notificationDropdown.css'
import './styles/studentDashboardCleanup.css'
import './styles/mobileDirectoryCards.css'
import App from './App.jsx'
import { installCookieCsrfFetchGuard } from './services/installCookieCsrfFetchGuard'
import { applyAccessibilityPreferences, getSavedAccessibilityPreferences, syncSystemThemePreference } from './utils/accessibilityPreferences'

installCookieCsrfFetchGuard();
applyAccessibilityPreferences(getSavedAccessibilityPreferences());
syncSystemThemePreference();

const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
const visualViewport = window.visualViewport;
const rootElement = document.getElementById('root');
const PWA_SCROLLABLE_SELECTOR = [
  "#root",
  ".auth-surface",
  ".public-page-shell",
  "#dashboard-scroll-viewport",
  "[data-pwa-scroll-root='true']",
  "[data-guide-page='true']",
  "[data-modal-scroll-container='true']",
  "[class*='overflow-x-auto']",
  "[class*='overflow-y-auto']",
  ".chart-interactive-scroll",
  ".mobile-scroll-list",
  ".table-wrap",
].join(", ");

let stableViewportHeight = Math.max(
  window.innerHeight,
  visualViewport?.height || 0,
);
let stableViewportWidth = visualViewport?.width || window.innerWidth;

const isStandalonePwa = () => Boolean(
  standaloneQuery?.matches || window.navigator?.standalone === true
);

const isFormControlFocused = () => {
  const element = document.activeElement;
  return Boolean(
    element &&
    ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName)
  );
};

const syncPwaViewportMetrics = () => {
  const standalone = isStandalonePwa();
  document.documentElement.dataset.standalonePwa = String(standalone);

  if (!standalone) {
    document.documentElement.style.removeProperty(
      "--pwa-fixed-bottom-compensation",
    );
    return;
  }

  const viewportHeight = visualViewport?.height || window.innerHeight;
  const viewportWidth = visualViewport?.width || window.innerWidth;
  const viewportOffsetTop = visualViewport?.offsetTop || 0;

  if (Math.abs(viewportWidth - stableViewportWidth) > 48) {
    stableViewportWidth = viewportWidth;
    stableViewportHeight = Math.max(window.innerHeight, viewportHeight);
  }

  const keyboardGap = stableViewportHeight - viewportHeight - viewportOffsetTop;
  const keyboardOpen = isFormControlFocused() && keyboardGap > 120;

  if (!keyboardOpen) {
    stableViewportHeight = Math.max(window.innerHeight, viewportHeight);
  }

  document.documentElement.style.setProperty(
    "--pwa-fixed-bottom-compensation",
    `${keyboardOpen ? Math.max(0, keyboardGap) : 0}px`,
  );
};

const applyStandaloneScrollSupport = () => {
  syncPwaViewportMetrics();
  if (!isStandalonePwa()) return;

  document.documentElement.style.touchAction = "auto";
  document.body.style.touchAction = "auto";
  document.querySelectorAll(PWA_SCROLLABLE_SELECTOR).forEach((element) => {
    element.style.webkitOverflowScrolling = "touch";
    element.style.touchAction = "auto";
  });
};

const handlePwaPlanNavigation = (event) => {
  if (!isStandalonePwa()) return;

  const anchor = event.target?.closest?.(
    'a[href^="#subscription-plan-"]',
  );
  if (!anchor) return;

  const targetId = anchor.getAttribute("href")?.slice(1);
  const target = targetId ? document.getElementById(targetId) : null;
  if (!target) return;

  event.preventDefault();
  window.requestAnimationFrame(() => {
    target.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "start",
    });
  });
};

applyStandaloneScrollSupport();
const pwaScrollObserver = new MutationObserver(applyStandaloneScrollSupport);
if (rootElement) {
  pwaScrollObserver.observe(rootElement, {
    childList: true,
    subtree: true,
  });
}
standaloneQuery?.addEventListener?.("change", applyStandaloneScrollSupport);
window.addEventListener("pageshow", applyStandaloneScrollSupport);
window.addEventListener("orientationchange", applyStandaloneScrollSupport);
window.addEventListener("resize", syncPwaViewportMetrics);
visualViewport?.addEventListener?.("resize", syncPwaViewportMetrics);
visualViewport?.addEventListener?.("scroll", syncPwaViewportMetrics);
document.addEventListener("visibilitychange", applyStandaloneScrollSupport);
document.addEventListener("focusin", syncPwaViewportMetrics);
document.addEventListener("focusout", () => {
  window.setTimeout(syncPwaViewportMetrics, 80);
});
document.addEventListener("click", handlePwaPlanNavigation, true);

createRoot(rootElement).render(<App />)