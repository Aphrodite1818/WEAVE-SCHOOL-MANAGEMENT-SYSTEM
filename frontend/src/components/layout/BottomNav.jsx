import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Home, CalendarDays, MessageSquare, Menu, BookOpen, FileText } from "lucide-react";
import { cn } from "../../utils/cn";
import { scrollDashboardViewportToTop } from "../../utils/dashboardScroll";

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

const isStandaloneDisplay = () => {
  if (typeof window === "undefined") return false;

  const standaloneMedia = window.matchMedia?.("(display-mode: standalone)")?.matches;
  const fullscreenMedia = window.matchMedia?.("(display-mode: fullscreen)")?.matches;
  const iosStandalone = window.navigator?.standalone === true;

  return Boolean(standaloneMedia || fullscreenMedia || iosStandalone);
};

function BottomNav({ role, onOpenMenu }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [isInstalledApp, setIsInstalledApp] = useState(isStandaloneDisplay);
  const [indicatorStyle, setIndicatorStyle] = useState({
    width: 0,
    transform: "translateX(0px)",
    opacity: 0,
  });
  const navRef = useRef(null);
  const itemRefs = useRef({});
  const items = bottomNavConfig[role] || bottomNavConfig.admin;

  const updateIndicator = useCallback(() => {
    const navElement = navRef.current;
    const activeItem = items.find((item) => {
      return (
        location.pathname === item.to ||
        (item.to !== "/" && location.pathname.startsWith(`${item.to}/`))
      );
    });

    const activeElement = activeItem ? itemRefs.current[activeItem.to] : null;

    if (!navElement || !activeElement) {
      setIndicatorStyle((current) => ({ ...current, opacity: 0 }));
      return;
    }

    const itemRect = activeElement.getBoundingClientRect();

    setIndicatorStyle({
      width: itemRect.width,
      transform: `translateX(${activeElement.offsetLeft}px)`,
      opacity: 1,
    });
  }, [items, location.pathname]);

  const scheduleIndicatorUpdate = useCallback(() => {
    if (typeof window === "undefined") return;

    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        updateIndicator();
      });
    });
  }, [updateIndicator]);

  useEffect(() => {
    const standaloneQuery = window.matchMedia?.("(display-mode: standalone)");
    const fullscreenQuery = window.matchMedia?.("(display-mode: fullscreen)");
    const updateDisplayMode = () => setIsInstalledApp(isStandaloneDisplay());

    updateDisplayMode();
    standaloneQuery?.addEventListener?.("change", updateDisplayMode);
    fullscreenQuery?.addEventListener?.("change", updateDisplayMode);

    return () => {
      standaloneQuery?.removeEventListener?.("change", updateDisplayMode);
      fullscreenQuery?.removeEventListener?.("change", updateDisplayMode);
    };
  }, []);

  useLayoutEffect(() => {
    if (!isInstalledApp) return;
    scheduleIndicatorUpdate();
  }, [isInstalledApp, scheduleIndicatorUpdate]);

  useEffect(() => {
    if (!isInstalledApp) return undefined;

    const handleResize = () => scheduleIndicatorUpdate();
    const handleVisibilityChange = () => {
      if (!document.hidden) scheduleIndicatorUpdate();
    };

    window.addEventListener("resize", handleResize);
    window.addEventListener("orientationchange", handleResize);
    window.addEventListener("pageshow", handleResize);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("orientationchange", handleResize);
      window.removeEventListener("pageshow", handleResize);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isInstalledApp, scheduleIndicatorUpdate]);

  const handleItemClick = useCallback(
    (event, item, isActive) => {
      event.preventDefault();

      if (isActive) {
        scrollDashboardViewportToTop("smooth");
        return;
      }

      navigate(item.to);
    },
    [navigate]
  );

  if (!isInstalledApp) return null;

  return (
    <nav
      data-mobile-bottom-nav="true"
      className="fixed inset-x-0 bottom-[max(0.35rem,env(safe-area-inset-bottom))] z-40 px-2 pb-1 pt-1.5 backdrop-blur-xl md:hidden"
      aria-label="Primary mobile navigation"
    >
      <div
        ref={navRef}
        className="relative mx-auto flex w-full max-w-[30rem] items-center gap-2 rounded-[1.7rem] border border-border/70 bg-surface/95 p-1.5 shadow-[0_18px_48px_rgba(15,23,42,0.22)]"
      >
        <span
          aria-hidden="true"
          className="bottom-nav-indicator pointer-events-none absolute bottom-1.5 left-0 top-1.5 z-0 rounded-[1.35rem] bg-surface-raised shadow-[inset_0_1px_0_rgba(255,255,255,0.25),0_10px_22px_rgba(15,23,42,0.14)]"
          style={indicatorStyle}
        />
        {items.map((item) => {
          const Icon = item.icon;
          const isActive =
            location.pathname === item.to ||
            (item.to !== "/" && location.pathname.startsWith(`${item.to}/`));

          return (
            <button
              type="button"
              key={item.label}
              onClick={(event) => handleItemClick(event, item, isActive)}
              ref={(node) => {
                itemRefs.current[item.to] = node;
              }}
              aria-current={isActive ? "page" : undefined}
              aria-label={item.label}
              className={cn(
                "relative z-10 flex min-h-[3.7rem] flex-1 touch-manipulation select-none flex-col items-center justify-center gap-1 rounded-[1.35rem] px-2.5 py-2 text-center transition-colors duration-200 ease-out",
                isActive
                  ? "text-text"
                  : "text-text-muted hover:bg-surface-muted/80 hover:text-text"
              )}
            >
              <Icon className={cn("pointer-events-none h-5 w-5 shrink-0 transition-colors duration-200 ease-out", isActive && "text-primary")} />
              <span className={cn("pointer-events-none max-w-full truncate text-[11px] font-bold leading-tight transition-colors duration-200 ease-out", isActive && "text-text")}>
                {item.label}
              </span>
            </button>
          );
        })}
        <button
          type="button"
          onClick={onOpenMenu}
          className="relative z-10 flex min-h-[3.7rem] flex-1 touch-manipulation select-none flex-col items-center justify-center gap-1 rounded-[1.35rem] px-2.5 py-2 text-text-muted transition-colors duration-200 ease-out hover:bg-surface-muted/80 hover:text-text"
          aria-label="Open full navigation menu"
        >
          <Menu className="pointer-events-none h-5 w-5 shrink-0" />
          <span className="pointer-events-none text-[11px] font-bold leading-tight">Menu</span>
        </button>
      </div>
    </nav>
  );
}

export default BottomNav;
