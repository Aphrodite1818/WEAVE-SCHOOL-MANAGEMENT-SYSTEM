import { createRoot } from 'react-dom/client'
import './index.css'
import './styles/mobileDashboard.css'
import './styles/mobileOverrides.css'
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
const PWA_SCROLLABLE_SELECTOR = [
  "#root",
  ".auth-surface",
  ".public-page-shell",
  "[class*='overflow-x-auto']",
  "[class*='overflow-y-auto']",
  ".chart-interactive-scroll",
  ".mobile-scroll-list",
  ".table-wrap",
].join(", ");

const applyStandaloneScrollSupport = () => {
  const isStandalone = Boolean(
    standaloneQuery?.matches || window.navigator?.standalone === true
  );
  document.documentElement.dataset.standalonePwa = String(isStandalone);
  if (!isStandalone) return;

  document.documentElement.style.touchAction = "auto";
  document.body.style.touchAction = "auto";
  document.querySelectorAll(PWA_SCROLLABLE_SELECTOR).forEach((element) => {
    element.style.webkitOverflowScrolling = "touch";
  });
};

const updateStandaloneDisplayMode = () => {
  applyStandaloneScrollSupport();
};

updateStandaloneDisplayMode();
const pwaScrollObserver = new MutationObserver(applyStandaloneScrollSupport);
pwaScrollObserver.observe(document.getElementById('root'), {
  childList: true,
  subtree: true,
});
standaloneQuery?.addEventListener?.("change", updateStandaloneDisplayMode);
window.addEventListener("pageshow", updateStandaloneDisplayMode);
window.addEventListener("orientationchange", applyStandaloneScrollSupport);
document.addEventListener("visibilitychange", updateStandaloneDisplayMode);

createRoot(document.getElementById('root')).render(<App />)