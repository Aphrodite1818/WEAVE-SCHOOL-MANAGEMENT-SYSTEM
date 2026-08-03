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

const isStandalonePwa = () => Boolean(
  standaloneQuery?.matches || window.navigator?.standalone === true
);

const syncStandaloneDisplayMode = () => {
  document.documentElement.dataset.standalonePwa = String(isStandalonePwa());
};

const applyStandaloneScrollSupport = () => {
  syncStandaloneDisplayMode();
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
document.addEventListener("visibilitychange", applyStandaloneScrollSupport);
document.addEventListener("click", handlePwaPlanNavigation, true);

createRoot(rootElement).render(<App />)