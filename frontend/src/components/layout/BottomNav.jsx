import {
  memo,
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { Link, useLocation } from "react-router-dom";
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
  const navRef = useRef(null);
  const itemRefs = useRef({});
  const lastViewportWidth = useRef(
    typeof window === "undefined" ? 0 : window.innerWidth
  );
  const items = bottomNavConfig[role] || bottomNavConfig.admin;

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

  const setIndicatorFromTarget = useCallback((target) => {
    if (!target) return;
    setIndicatorStyle(getIndicatorStyleForElement(target));
  }, []);

  const scheduleIndicatorUpdate = useCallback(() => {
    if (typeof window === "undefined") return;

    window.requestAnimationFrame(() => {
      updateIndicator();
    });
  }, [updateIndicator]);

  useLayoutEffect(() => {
    scheduleIndicatorUpdate();
  }, [scheduleIndicatorUpdate]);

  useLayoutEffect(() => {
    const handleResize = () => {
      // Mobile browsers fire `resize` when the address bar collapses/expands
      // during scroll — that only changes viewport height, not width. Re-running
      // indicator layout in that moment can shift the tap target under the
      // user's finger and cause the browser to drop the click. Only react when
      // the width actually changed (a real rotation/breakpoint change).
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

  const handleItemPointerDown = useCallback(
    (event, item) => {
      if (isRouteActive(location.pathname, item.to)) return;
      setIndicatorFromTarget(event.currentTarget);
    },
    [location.pathname, setIndicatorFromTarget]
  );

  const handleItemClick = useCallback(
    (event, item) => {
      if (!isRouteActive(location.pathname, item.to)) {
        setIndicatorFromTarget(event.currentTarget);
        return;
      }

      event.preventDefault();
      scrollDashboardViewportToTop("auto");
    },
    [location.pathname, setIndicatorFromTarget]
  );

  return (
    <nav
      data-mobile-bottom-nav="true"
      className="fixed inset-x-0 bottom-0 z-40 px-2 pb-[max(0.25rem,env(safe-area-inset-bottom))] pt-1.5 md:hidden"
      aria-label="Primary installed app navigation"
    >
      <div
        ref={navRef}
        className="relative mx-auto flex w-full max-w-[31rem] items-center gap-2 rounded-[2rem] border border-border/70 bg-surface/95 p-2 shadow-[0_12px_28px_rgba(15,23,42,0.16)]"
      >
        <span
          aria-hidden="true"
          className="bottom-nav-indicator pointer-events-none absolute bottom-2 left-0 top-2 z-0 rounded-[1.6rem] bg-surface-raised shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_8px_18px_rgba(15,23,42,0.12)]"
          style={indicatorStyle}
        />
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = isRouteActive(location.pathname, item.to);

          return (
            <Link
              key={item.label}
              to={item.to}
              onPointerDown={(event) => handleItemPointerDown(event, item)}
              onClick={(event) => handleItemClick(event, item)}
              ref={(node) => {
                itemRefs.current[item.to] = node;
              }}
              aria-current={isActive ? "page" : undefined}
              aria-label={item.label}
              className={cn(
                "relative z-10 flex min-h-16 flex-1 touch-manipulation select-none flex-col items-center justify-center gap-1 rounded-[1.6rem] px-2.5 py-2.5 text-center transition-colors duration-150 ease-out",
                isActive
                  ? "text-text"
                  : "text-text-muted hover:bg-surface-muted/80 hover:text-text"
              )}
            >
              <Icon className={cn("pointer-events-none h-[1.375rem] w-[1.375rem] shrink-0 transition-colors duration-150 ease-out", isActive && "text-primary")} />
              <span className={cn("pointer-events-none max-w-full truncate text-[11.5px] font-bold leading-tight transition-colors duration-150 ease-out", isActive && "text-text")}>
                {item.label}
              </span>
            </Link>
          );
        })}
        <button
          type="button"
          onClick={onOpenMenu}
          className="relative z-10 flex min-h-16 flex-1 touch-manipulation select-none flex-col items-center justify-center gap-1 rounded-[1.6rem] px-2.5 py-2.5 text-text-muted transition-colors duration-150 ease-out hover:bg-surface-muted/80 hover:text-text"
          aria-label="Open full navigation menu"
        >
          <Menu className="pointer-events-none h-[1.375rem] w-[1.375rem] shrink-0" />
          <span className="pointer-events-none text-[11.5px] font-bold leading-tight">Menu</span>
        </button>
      </div>
    </nav>
  );
}

export default memo(BottomNav);
