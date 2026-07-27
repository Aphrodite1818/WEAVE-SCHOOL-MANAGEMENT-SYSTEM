import { createRoot } from 'react-dom/client'
import './index.css'
import './styles/mobileDashboard.css'
import './styles/mobileOverrides.css'
import './styles/brandAssets.css'
import './styles/notificationDropdown.css'
import './styles/studentDashboardCleanup.css'
import App from './App.jsx'
import { applyAccessibilityPreferences, getSavedAccessibilityPreferences, syncSystemThemePreference } from './utils/accessibilityPreferences'

applyAccessibilityPreferences(getSavedAccessibilityPreferences());
syncSystemThemePreference();

const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
const updateStandaloneDisplayMode = () => {
  const isStandalone = Boolean(
    standaloneQuery?.matches || window.navigator?.standalone === true
  );
  document.documentElement.dataset.standalonePwa = String(isStandalone);
};

updateStandaloneDisplayMode();
standaloneQuery?.addEventListener?.("change", updateStandaloneDisplayMode);
window.addEventListener("pageshow", updateStandaloneDisplayMode);
document.addEventListener("visibilitychange", updateStandaloneDisplayMode);

createRoot(document.getElementById('root')).render(<App />)