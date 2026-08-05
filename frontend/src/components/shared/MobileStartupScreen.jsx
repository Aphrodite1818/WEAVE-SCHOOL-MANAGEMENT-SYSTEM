
import { useEffect, useState } from "react";

const MIN_STARTUP_DURATION_MS = 300;
const MAX_STARTUP_DURATION_MS = 1200;
const STARTUP_SEEN_KEY = "weave:pwa-startup-seen";

function isMobileStandaloneViewport() {
  if (typeof window === "undefined") return false;
  const mobileQuery = window.matchMedia("(max-width: 767px)");
  const standaloneQuery = window.matchMedia("(display-mode: standalone)");
  return mobileQuery.matches && (
    standaloneQuery.matches || window.navigator?.standalone === true
  );
}

function shouldShowStartup() {
  if (!isMobileStandaloneViewport()) return false;
  return window.sessionStorage.getItem(STARTUP_SEEN_KEY) !== "true";
}

function MobileStartupScreen() {
  const [visible, setVisible] = useState(() => shouldShowStartup());

  useEffect(() => {
    if (!visible || typeof window === "undefined") return undefined;
    window.sessionStorage.setItem(STARTUP_SEEN_KEY, "true");

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const minimumDuration = reducedMotion ? 120 : MIN_STARTUP_DURATION_MS;
    const startedAt = performance.now();
    let minimumElapsed = false;
    let shellReady = Boolean(document.querySelector("[data-dashboard-role]"));

    const maybeHide = () => {
      if (minimumElapsed && shellReady) setVisible(false);
    };
    const minimumTimer = window.setTimeout(() => {
      minimumElapsed = true;
      maybeHide();
    }, minimumDuration);
    const maximumTimer = window.setTimeout(
      () => setVisible(false),
      Math.max(MAX_STARTUP_DURATION_MS - (performance.now() - startedAt), minimumDuration),
    );
    const observer = new MutationObserver(() => {
      shellReady = Boolean(document.querySelector("[data-dashboard-role]"));
      maybeHide();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      window.clearTimeout(minimumTimer);
      window.clearTimeout(maximumTimer);
    };
  }, [visible]);

  if (!visible) return null;
  return (
    <div className="mobile-startup-screen" role="status" aria-label="Starting Weave">
      <div className="mobile-startup-word" aria-hidden="true">
        {"WEAVE".split("").map((letter, index) => (
          <span key={`${letter}-${index}`} style={{ "--letter-index": index }}>
            {letter}
          </span>
        ))}
      </div>
      <div className="mobile-startup-loader" aria-hidden="true" />
    </div>
  );
}

export default MobileStartupScreen;
