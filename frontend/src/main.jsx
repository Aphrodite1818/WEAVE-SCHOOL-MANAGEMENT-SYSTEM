import { createRoot } from 'react-dom/client'
import './index.css'
import './styles/mobileDashboard.css'
import './styles/mobileOverrides.css'
import './styles/brandAssets.css'
import './styles/notificationDropdown.css'
import './styles/studentDashboardCleanup.css'
import './styles/mobileDirectoryCards.css'
import './styles/pwaInteractions.css'
import './styles/mobilePwaStability.css'
import App from './App.jsx'
import { installCookieCsrfFetchGuard } from './services/installCookieCsrfFetchGuard'
import { applyAccessibilityPreferences, getSavedAccessibilityPreferences, syncSystemThemePreference } from './utils/accessibilityPreferences'
import { installMobilePwaStability } from './utils/mobilePwaStability'

installCookieCsrfFetchGuard();
applyAccessibilityPreferences(getSavedAccessibilityPreferences());
syncSystemThemePreference();
installMobilePwaStability();

const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");

const isStandalonePwa = () => Boolean(
  standaloneQuery?.matches || window.navigator?.standalone === true
);

const syncStandaloneDisplayMode = () => {
  document.documentElement.dataset.standalonePwa = String(isStandalonePwa());
};

const registerPwaServiceWorker = () => {
  if (
    !import.meta.env.PROD ||
    !window.isSecureContext ||
    !("serviceWorker" in window.navigator)
  ) {
    return;
  }

  window.addEventListener(
    "load",
    () => {
      window.navigator.serviceWorker
        .register("/sw.js", { scope: "/", updateViaCache: "none" })
        .catch((error) => {
          console.warn("PWA service worker registration failed", error);
        });
    },
    { once: true },
  );
};

syncStandaloneDisplayMode();
registerPwaServiceWorker();
standaloneQuery?.addEventListener?.("change", syncStandaloneDisplayMode);
window.addEventListener("pageshow", syncStandaloneDisplayMode);
document.addEventListener("visibilitychange", syncStandaloneDisplayMode);

createRoot(document.getElementById('root')).render(<App />)