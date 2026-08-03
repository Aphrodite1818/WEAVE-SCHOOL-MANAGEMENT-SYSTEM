import { createRoot } from 'react-dom/client'
import './index.css'
import './styles/mobileDashboard.css'
import './styles/mobileOverrides.css'
import './styles/brandAssets.css'
import './styles/notificationDropdown.css'
import './styles/studentDashboardCleanup.css'
import './styles/mobileDirectoryCards.css'
import './styles/pwaInteractions.css'
import App from './App.jsx'
import { installCookieCsrfFetchGuard } from './services/installCookieCsrfFetchGuard'
import { applyAccessibilityPreferences, getSavedAccessibilityPreferences, syncSystemThemePreference } from './utils/accessibilityPreferences'

installCookieCsrfFetchGuard();
applyAccessibilityPreferences(getSavedAccessibilityPreferences());
syncSystemThemePreference();

const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");

const isStandalonePwa = () => Boolean(
  standaloneQuery?.matches || window.navigator?.standalone === true
);

const syncStandaloneDisplayMode = () => {
  document.documentElement.dataset.standalonePwa = String(isStandalonePwa());
};

syncStandaloneDisplayMode();
standaloneQuery?.addEventListener?.("change", syncStandaloneDisplayMode);
window.addEventListener("pageshow", syncStandaloneDisplayMode);
document.addEventListener("visibilitychange", syncStandaloneDisplayMode);

createRoot(document.getElementById('root')).render(<App />)