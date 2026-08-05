import { createRoot } from "react-dom/client";
import "./index.css";
import "./styles/mobileDashboard.css";
import "./styles/mobileOverrides.css";
import "./styles/brandAssets.css";
import "./styles/notificationDropdown.css";
import "./styles/studentDashboardCleanup.css";
import "./styles/mobileDirectoryCards.css";
import "./styles/pwaInteractions.css";
import "./styles/mobilePwaStability.css";
import "./styles/mobilePlatformFixes.css";
import App from "./App.jsx";
import {
  applyPublicPricingCatalogue,
  resetPublicPricingPlans,
} from "./features/subscriptions/pricingCatalogueRuntime";
import { installCookieCsrfFetchGuard } from "./services/installCookieCsrfFetchGuard";
import { subscriptionService } from "./services/subscriptionService";
import {
  applyAccessibilityPreferences,
  getSavedAccessibilityPreferences,
  syncSystemThemePreference,
} from "./utils/accessibilityPreferences";
import { installMobilePwaStability } from "./utils/mobilePwaStability";
import { installThemeChromeSync } from "./utils/themeChromeSync";

installCookieCsrfFetchGuard();
applyAccessibilityPreferences(getSavedAccessibilityPreferences());
syncSystemThemePreference();
installMobilePwaStability();
installThemeChromeSync();
resetPublicPricingPlans();

const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");

const isStandalonePwa = () =>
  Boolean(standaloneQuery?.matches || window.navigator?.standalone === true);

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

const root = createRoot(document.getElementById("root"));
const renderApp = () => root.render(<App />);

renderApp();

subscriptionService
  .getPublicPlans()
  .then((catalogue) => {
    applyPublicPricingCatalogue(catalogue);
    renderApp();
  })
  .catch((error) => {
    console.warn("Subscription pricing catalogue could not be loaded", {
      message: error?.message || "unknown error",
    });
  });
