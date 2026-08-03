const KEYBOARD_THRESHOLD_PX = 120;
const ROUTE_CHANGE_EVENT = "weave:routechange";
const INSTALLATION_KEY = "__weaveMobilePwaStabilityCleanup";
const PRICING_ROUTE = "/admin/billing/plans";
const EDITABLE_SELECTOR = [
  "input:not([type='button']):not([type='checkbox']):not([type='file']):not([type='hidden']):not([type='radio']):not([type='reset']):not([type='submit'])",
  "textarea",
  "select",
  "[contenteditable='true']",
].join(",");
const INTERNAL_SCROLL_SELECTOR = [
  "[data-modal-scroll-container='true']",
  "#dashboard-scroll-viewport",
  "[data-pwa-scroll-root='true']",
  ".public-page-shell",
  ".auth-surface",
  "[data-guide-page='true']",
].join(",");

const isStandalonePwa = () => Boolean(
  window.matchMedia?.("(display-mode: standalone)")?.matches
    || window.navigator?.standalone === true,
);

const detectPwaPlatform = () => {
  const userAgent = window.navigator?.userAgent || "";
  const platform = window.navigator?.userAgentData?.platform
    || window.navigator?.platform
    || "";
  const iPadOsDesktopMode =
    platform === "MacIntel" && Number(window.navigator?.maxTouchPoints || 0) > 1;

  if (/iPad|iPhone|iPod/i.test(userAgent) || iPadOsDesktopMode) return "ios";
  if (/Android/i.test(userAgent) || /Android/i.test(platform)) return "android";
  return "other";
};

const isEditableElement = (element) => Boolean(
  element instanceof Element && element.matches(EDITABLE_SELECTOR),
);

const resetHorizontalScroll = () => {
  const scrollingElement = document.scrollingElement;
  if (scrollingElement) {
    scrollingElement.scrollTo({
      left: 0,
      top: scrollingElement.scrollTop,
      behavior: "auto",
    });
  }

  document.documentElement.scrollLeft = 0;
  document.body.scrollLeft = 0;
  document.querySelectorAll(".public-page-shell").forEach((shell) => {
    shell.scrollLeft = 0;
  });
};

const removePricingMarkers = () => {
  document.querySelectorAll("[data-pricing-tabs-scroll='true']").forEach((element) => {
    delete element.dataset.pricingTabsScroll;
  });
  document.querySelectorAll("[data-pricing-card-carousel='true']").forEach((element) => {
    delete element.dataset.pricingCardCarousel;
  });
};

const markPricingScrollRegions = () => {
  if (window.location.pathname !== PRICING_ROUTE) return;

  const planCards = [...document.querySelectorAll("article[id^='subscription-plan-']")];
  const cardCarousel = planCards[0]?.parentElement;
  if (cardCarousel) cardCarousel.dataset.pricingCardCarousel = "true";

  const firstPlanTab = document.querySelector("a[href^='#subscription-plan-']");
  const tabsScrollRegion = firstPlanTab?.parentElement?.parentElement;
  if (tabsScrollRegion) tabsScrollRegion.dataset.pricingTabsScroll = "true";
};

const patchHistory = (onRouteChange) => {
  const originalPushState = window.history.pushState;
  const originalReplaceState = window.history.replaceState;

  const wrap = (original) => function wrappedHistoryMethod(...args) {
    const result = original.apply(this, args);
    window.dispatchEvent(new Event(ROUTE_CHANGE_EVENT));
    return result;
  };

  window.history.pushState = wrap(originalPushState);
  window.history.replaceState = wrap(originalReplaceState);
  window.addEventListener("popstate", onRouteChange);
  window.addEventListener(ROUTE_CHANGE_EVENT, onRouteChange);

  return () => {
    window.history.pushState = originalPushState;
    window.history.replaceState = originalReplaceState;
    window.removeEventListener("popstate", onRouteChange);
    window.removeEventListener(ROUTE_CHANGE_EVENT, onRouteChange);
  };
};

export const installMobilePwaStability = () => {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return () => {};
  }

  if (window[INSTALLATION_KEY]) return window[INSTALLATION_KEY];

  const root = document.documentElement;
  const visualViewport = window.visualViewport;
  const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
  const reducedMotionQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  let stableLayoutHeight = 0;
  let stableViewportWidth = 0;
  let keyboardOpen = false;
  let currentPath = window.location.pathname;
  let frameId = 0;
  let orientationTimer = 0;

  const setStableLayoutHeight = ({ force = false } = {}) => {
    if (!isStandalonePwa() || (keyboardOpen && !force)) return;

    const nextHeight = Math.max(
      Number(window.innerHeight || 0),
      Number(document.documentElement.clientHeight || 0),
    );
    if (nextHeight <= 0) return;

    stableLayoutHeight = nextHeight;
    stableViewportWidth = Number(window.innerWidth || 0);
    root.style.setProperty("--pwa-layout-height", `${nextHeight}px`);
  };

  const syncEnvironmentMarkers = () => {
    const standalone = isStandalonePwa();
    root.dataset.standalonePwa = String(standalone);
    root.dataset.pwaPlatform = detectPwaPlatform();

    if (standalone && stableLayoutHeight <= 0) {
      setStableLayoutHeight({ force: true });
    }
  };

  const keepFocusedElementVisible = () => {
    const activeElement = document.activeElement;
    if (!keyboardOpen || !visualViewport || !isEditableElement(activeElement)) return;

    const scrollContainer = activeElement.closest(INTERNAL_SCROLL_SELECTOR);
    if (!scrollContainer) return;

    const rect = activeElement.getBoundingClientRect();
    const visibleTop = visualViewport.offsetTop + 16;
    const visibleBottom = visualViewport.offsetTop + visualViewport.height - 16;
    let delta = 0;

    if (rect.bottom > visibleBottom) delta = rect.bottom - visibleBottom;
    if (rect.top < visibleTop) delta = rect.top - visibleTop;
    if (Math.abs(delta) < 1) return;

    scrollContainer.scrollBy({
      top: delta,
      left: 0,
      behavior: reducedMotionQuery?.matches ? "auto" : "smooth",
    });
  };

  const syncKeyboardState = () => {
    if (!isStandalonePwa() || !visualViewport || stableLayoutHeight <= 0) {
      keyboardOpen = false;
      root.dataset.keyboardOpen = "false";
      root.style.setProperty("--virtual-keyboard-height", "0px");
      return;
    }

    const activeElement = document.activeElement;
    const keyboardHeight = Math.max(
      0,
      Math.round(
        stableLayoutHeight
          - Number(visualViewport.height || 0)
          - Number(visualViewport.offsetTop || 0),
      ),
    );
    keyboardOpen = isEditableElement(activeElement)
      && keyboardHeight >= KEYBOARD_THRESHOLD_PX;

    root.dataset.keyboardOpen = String(keyboardOpen);
    root.style.setProperty(
      "--virtual-keyboard-height",
      keyboardOpen ? `${keyboardHeight}px` : "0px",
    );

    if (keyboardOpen) {
      window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(keepFocusedElementVisible);
    }
  };

  const syncPricingRoute = () => {
    const nextPath = window.location.pathname;
    const pricingBoundaryChanged =
      currentPath === PRICING_ROUTE || nextPath === PRICING_ROUTE;

    if (pricingBoundaryChanged) resetHorizontalScroll();
    if (nextPath !== PRICING_ROUTE) removePricingMarkers();

    currentPath = nextPath;
    window.requestAnimationFrame(markPricingScrollRegions);
  };

  const handleViewportResize = () => {
    const widthChanged = Number(window.innerWidth || 0) !== stableViewportWidth;
    syncKeyboardState();
    if (!keyboardOpen && widthChanged) setStableLayoutHeight({ force: true });
  };

  const handleOrientationChange = () => {
    window.clearTimeout(orientationTimer);
    orientationTimer = window.setTimeout(() => {
      keyboardOpen = false;
      root.dataset.keyboardOpen = "false";
      root.style.setProperty("--virtual-keyboard-height", "0px");
      setStableLayoutHeight({ force: true });
      syncKeyboardState();
      resetHorizontalScroll();
    }, 250);
  };

  const handleVisibilityChange = () => {
    if (document.hidden) return;
    syncEnvironmentMarkers();
    setStableLayoutHeight({ force: true });
    syncKeyboardState();
    syncPricingRoute();
  };

  const handleFocusChange = () => {
    window.cancelAnimationFrame(frameId);
    frameId = window.requestAnimationFrame(syncKeyboardState);
  };

  const observer = new MutationObserver(() => {
    if (window.location.pathname === PRICING_ROUTE) {
      window.requestAnimationFrame(markPricingScrollRegions);
    }
  });

  const unpatchHistory = patchHistory(syncPricingRoute);

  syncEnvironmentMarkers();
  setStableLayoutHeight({ force: true });
  syncKeyboardState();
  syncPricingRoute();

  observer.observe(document.getElementById("root") || document.body, {
    childList: true,
    subtree: true,
  });
  standaloneQuery?.addEventListener?.("change", syncEnvironmentMarkers);
  visualViewport?.addEventListener("resize", syncKeyboardState);
  visualViewport?.addEventListener("scroll", syncKeyboardState);
  window.addEventListener("resize", handleViewportResize);
  window.addEventListener("orientationchange", handleOrientationChange);
  window.addEventListener("pageshow", handleVisibilityChange);
  document.addEventListener("visibilitychange", handleVisibilityChange);
  document.addEventListener("focusin", handleFocusChange);
  document.addEventListener("focusout", handleFocusChange);

  const cleanup = () => {
    observer.disconnect();
    unpatchHistory();
    standaloneQuery?.removeEventListener?.("change", syncEnvironmentMarkers);
    visualViewport?.removeEventListener("resize", syncKeyboardState);
    visualViewport?.removeEventListener("scroll", syncKeyboardState);
    window.removeEventListener("resize", handleViewportResize);
    window.removeEventListener("orientationchange", handleOrientationChange);
    window.removeEventListener("pageshow", handleVisibilityChange);
    document.removeEventListener("visibilitychange", handleVisibilityChange);
    document.removeEventListener("focusin", handleFocusChange);
    document.removeEventListener("focusout", handleFocusChange);
    window.clearTimeout(orientationTimer);
    window.cancelAnimationFrame(frameId);
    removePricingMarkers();
    delete window[INSTALLATION_KEY];
  };

  window[INSTALLATION_KEY] = cleanup;
  return cleanup;
};
