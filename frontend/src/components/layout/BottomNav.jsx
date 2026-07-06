import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { Link, useLocation } from "react-router-dom";
import { Home, CalendarDays, MessageSquare, Menu, BookOpen, FileText } from "lucide-react";
import { cn } from "../../utils/cn";
import { scrollDashboardViewportToTop } from "../../utils/dashboardScroll";

const NAV_INDICATOR_COMMIT_DELAY_MS = 350;
const NAV_LOADING_SHOW_DELAY_MS = 80;
const NAV_LOADING_MIN_VISIBLE_MS = 300;
const NAV_LOADING_MAX_MS = 1200;

const bottomNavConfig = {
  admin: [
    { label: "Home", to: "/admin/dashboard", icon: Home },
    { label: "Calendar", to: "/admin/timetable", icon: CalendarDays },
    { label: "Messages", to: "/admin/messages", icon: MessageSquare },
  ],
  teacher: [
    { label: "Home", to: "/teacher/dashboard", icon: Home },
    { label: "Rosters", to: "/teacher/students", icon: BookOpen },
    { label: "Scores", to: "/teacher/score-entry", icon: FileText },
  ],
  student: [
    { label: "Home", to: "/student/dashboard", icon: Home },
    { label: "Subjects", to: "/student/subjects", icon: BookOpen },
    { label: "Reports", to: "/student/report-cards", icon: FileText },
  ],
  parent: [
    { label: "Home", to: "/parent/dashboard", icon: Home },
    { label: "Results", to: "/parent/results", icon: BookOpen },
    { label: "Reports", to: "/parent/report-cards", icon: FileText },
  ],
  superadmin: [
    { label: "Home", to: "/superadmin/dashboard", icon: Home },
    { label: "Tenants", to: "/superadmin/dashboard", icon: BookOpen },
    { label: "Settings", to: "/superadmin/settings", icon: FileText },
  ],
};

const isRouteActive = (pathname, itemPath) =>
  pathname === itemPath ||
  (itemPath !== "/" && pathname.startsWith(`${itemPath}/`));

const getIndicatorStyleForElement = (element) => ({
  width: element.offsetWidth,
  transform: `translateX(${element.offsetLeft}px)`,
  opacity: 1,
});

function BottomNav({ role, onOpenMenu }) {
  const location = useLocation();
  const [indicatorStyle, setIndicatorStyle] = useState({
    width: 0,
    transform: "translateX(0px)",
    opacity: 0,
  });
  const [loadingVisible, setLoadingVisible] = useState(false);
  const navRef = useRef(null);
  const itemRefs = useRef({});
  const indicatorTimerRef = useRef(null);
  const loadingShowTimerRef = useRef(null);
  const loadingHideTimerRef = useRef(null);
  const loadingMaxTimerRef = useRef(null);
  const loadingStartedAtRef = useRef(0);
  const isTransitioningRef = useRef(false);
  const hasMountedRef = useRef(false);
  const lastViewportWidth = useRef(
    typeof window === "undefined" ? 0 : window.innerWidth
  );
  const items = bottomNavConfig[role] || bottomNavConfig.admin;

  const clearTimer = useCallback((timerRef) => {
    if (!timerRef.current) return;
    window.clearTimeout(timerRef.current);
    timerRef.current = null;
  }, []);

  const clearLoadingTimers = useCallback(() => {
    clearTimer(loadingShowTimerRef);
    clearTimer(loadingHideTimerRef);
    clearTimer(loadingMaxTimerRef);
  }, [clearTimer]);

  const updateIndicator = useCallback(() => {
    const navElement = navRef.current;
    const activeItem = items.find((item) =>
      isRouteActive(location.pathname, item.to)
    );

    const activeElement = activeItem ? itemRefs.current[activeItem.to] : null;

    if (!navElement || !activeElement) {
      setIndicatorStyle((current) => ({ ...current, opacity: 0 }));
      return;
    }

    setIndicatorStyle(getIndicatorStyleForElement(activeElement));
  }, [items, location.pathname]);

  const scheduleIndicatorUpdate = useCallback(() => {
    if (typeof window === "undefined") return;

    window.requestAnimationFrame(() => {
      updateIndicator();
    });
  }, [updateIndicator]);

  const finishNavigationFeedback = useCallback(() => {
    if (!isTransitioningRef.current) return;

    clearTimer(loadingShowTimerRef);
    clearTimer(loadingHideTimerRef);
    clearTimer(loadingMaxTimerRef);

    const elapsed = Date.now() - loadingStartedAtRef.current;
    const hideDelay = Math.max(NAV_LOADING_MIN_VISIBLE_MS - elapsed, 0);

    loadingHideTimerRef.current = window.setTimeout(() => {
      isTransitioningRef.current = false;
      setLoadingVisible(false);
      loadingHideTimerRef.current = null;
    }, hideDelay);
  }, [clearTimer]);

  const startNavigationFeedback = useCallback(() => {
    clearLoadingTimers();
    isTransitioningRef.current = true;
    loadingStartedAtRef.current = Date.now();

    loadingShowTimerRef.current = window.setTimeout(() => {
      if (!isTransitioningRef.current) return;
      setLoadingVisible(true);
      loadingShowTimerRef.current = null;
    }, NAV_LOADING_SHOW_DELAY_MS);

    loadingMaxTimerRef.current = window.setTimeout(() => {
      isTransitioningRef.current = false;
      setLoadingVisible(false);
      loadingMaxTimerRef.current = null;
    }, NAV_LOADING_MAX_MS);
  }, [clearLoadingTimers]);

  useLayoutEffect(() => {
    clearTimer(indicatorTimerRef);

    if (!hasMountedRef.current) {
      hasMountedRef.current = true;
      scheduleIndicatorUpdate();
      return undefined;
    }

    indicatorTimerRef.current = window.setTimeout(() => {
      scheduleIndicatorUpdate();
      finishNavigationFeedback();
      indicatorTimerRef.current = null;
    }, NAV_INDICATOR_COMMIT_DELAY_MS);

    return () => {
      clearTimer(indicatorTimerRef);
    };
  }, [clearTimer, finishNavigationFeedback, location.pathname, scheduleIndicatorUpdate]);

  useLayoutEffect(() => {
    const handleResize = () => {
      if (window.innerWidth === lastViewportWidth.current) return;
      lastViewportWidth.current = window.innerWidth;
      scheduleIndicatorUpdate();
    };
    const handleOrientationChange = () => {
      lastViewportWidth.current = window.innerWidth;
      scheduleIndicatorUpdate();
    };
    const handleVisibilityChange = () => {
      if (!document.hidden) scheduleIndicatorUpdate();
    };

    window.addEventListener("resize", handleResize);
    window.addEventListener("orientationchange", handleOrientationChange);
    window.addEventListener("pageshow", handleVisibilityChange);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("orientationchange", handleOrientationChange);
      window.removeEventListener("pageshow", handleVisibilityChange);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [scheduleIndicatorUpdate]);

  useEffect(() => {
    return () => {
      clearTimer(indicatorTimerRef);
      clearLoadingTimers();
    };
  }, [clearLoadingTimers, clearTimer]);

  const handleClick = useCallback(
    (event, item) => {
      if (isRouteActive(location.pathname, item.to)) {
        event.preventDefault();
        clearLoadingTimers();
        isTransitioningRef.current = false;
        setLoadingVisible(false);
        scrollDashboardViewportToTop("auto");
        return;
      }

      startNavigationFeedback();
    },
    [clearLoadingTimers, location.pathname, startNavigationFeedback]
  );

  return (
    <>
      {loadingVisible ? (
        <div
          className="pointer-events-none fixed inset-0 z-30 flex items-center justify-center bg-background/55 px-4 md:hidden"
          aria-hidden="true"
        >
          <div className="flex items-center gap-2 rounded-full bg-surface/95 px-4 py-2 text-xs font-semibold text-text-muted shadow-premium">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary/20 border-t-primary" />
            <span>Loading...</span>
          </div>
        </div>
      ) : null}

      <nav
        data-mobile-bottom-nav="true"
        className="bottom-nav-shell md:hidden"
        aria-label="Primary installed app navigation"
      >
        <div ref={navRef} className="bottom-nav-inner">
          <span
            aria-hidden="true"
            className="bottom-nav-indicator pointer-events-none absolute inset-y-1.5 left-0 z-0 rounded-2xl bg-primary/10"
            style={indicatorStyle}
          />

          {items.map((item) => {
            const Icon = item.icon;
            const isActive = isRouteActive(location.pathname, item.to);
            return (
              <Link
                key={item.label}
                to={item.to}
                ref={(node) => {
                  itemRefs.current[item.to] = node;
                }}
                onClick={(event) => handleClick(event, item)}
                aria-current={isActive ? "page" : undefined}
                aria-label={item.label}
                className={cn(
                  "bottom-nav-item",
                  isActive ? "text-primary" : "text-text-muted hover:text-text"
                )}
              >
                <Icon className={cn("h-5 w-5 shrink-0 transition-transform duration-150", isActive && "scale-110")} />
                <span className={cn("text-[10.5px] font-semibold leading-none transition-colors duration-150", isActive ? "text-primary" : "text-text-muted")}>
                  {item.label}
                </span>
              </Link>
            );
          })}

          <button
            type="button"
            onClick={onOpenMenu}
            className="bottom-nav-item text-text-muted hover:text-text"
            aria-label="Open full navigation menu"
          >
            <Menu className="h-5 w-5 shrink-0" />
            <span className="text-[10.5px] font-semibold leading-none">Menu</span>
          </button>
        </div>
      </nav>
    </>
  );
}

export default memo(BottomNav);
