import { useEffect, useState } from "react";

const STARTUP_DURATION_MS = 1550;

function isMobileStartupViewport() {
  if (typeof window === "undefined") return false;
  const mobileQuery = window.matchMedia("(max-width: 767px)");
  const standaloneQuery = window.matchMedia("(display-mode: standalone)");
  return mobileQuery.matches && (standaloneQuery.matches || window.navigator?.standalone === true);
}

function MobileStartupScreen() {
  const [visible, setVisible] = useState(() => isMobileStartupViewport());

  useEffect(() => {
    if (!visible || typeof window === "undefined") return undefined;

    const viewportQuery = window.matchMedia("(max-width: 767px)");
    const standaloneQuery = window.matchMedia("(display-mode: standalone)");
    const reducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const duration = reducedMotionQuery.matches ? 500 : STARTUP_DURATION_MS;

    const hideTimer = window.setTimeout(() => setVisible(false), duration);
    const syncViewport = () => {
      const isStandalone = standaloneQuery.matches || window.navigator?.standalone === true;
      if (!viewportQuery.matches || !isStandalone) setVisible(false);
    };

    viewportQuery.addEventListener?.("change", syncViewport);
    viewportQuery.addListener?.(syncViewport);
    standaloneQuery.addEventListener?.("change", syncViewport);
    standaloneQuery.addListener?.(syncViewport);

    return () => {
      window.clearTimeout(hideTimer);
      viewportQuery.removeEventListener?.("change", syncViewport);
      viewportQuery.removeListener?.(syncViewport);
      standaloneQuery.removeEventListener?.("change", syncViewport);
      standaloneQuery.removeListener?.(syncViewport);
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
