import { Link, useLocation } from "react-router-dom";
import { Home, CalendarDays, MessageSquare, Menu, BookOpen, FileText } from "lucide-react";
import { cn } from "../../utils/cn";

const bottomNavConfig = {
  admin: [
    { label: "Home", to: "/admin/dashboard", icon: Home },
    { label: "Calendar", to: "/admin/timetable", icon: CalendarDays },
    { label: "Messages", to: "/admin/messages", icon: MessageSquare },
  ],
  teacher: [
    { label: "Home", to: "/teacher/dashboard", icon: Home },
    { label: "Classes", to: "/teacher/classes", icon: BookOpen },
    { label: "Attendance", to: "/teacher/attendance", icon: CalendarDays },
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

function BottomNav({ role, onOpenMenu }) {
  const location = useLocation();
  const items = bottomNavConfig[role] || bottomNavConfig.admin;

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border/70 bg-surface/95 px-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))] pt-2 shadow-[0_-18px_50px_rgba(15,23,42,0.14)] backdrop-blur-xl md:hidden"
      aria-label="Primary mobile navigation"
    >
      <div className="mx-auto flex w-full max-w-[27rem] items-center gap-1 rounded-[1.65rem] border border-border/60 bg-surface p-1.5 shadow-sm">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive =
            location.pathname === item.to ||
            (item.to !== "/" && location.pathname.startsWith(`${item.to}/`));

          return (
            <Link
              key={item.label}
              to={item.to}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "flex min-h-[3.45rem] flex-1 flex-col items-center justify-center gap-0.5 rounded-[1.35rem] px-2 py-1.5 text-center transition-all duration-300 ease-out",
                isActive
                  ? "bg-surface-raised text-text shadow-[inset_0_1px_0_rgba(255,255,255,0.25),0_6px_18px_rgba(15,23,42,0.12)]"
                  : "text-text-muted hover:bg-surface-muted/80 hover:text-text"
              )}
            >
              <Icon className={cn("h-5 w-5 shrink-0 transition-colors duration-300 ease-out", isActive && "text-primary")} />
              <span className={cn("max-w-full truncate text-[10px] font-bold leading-tight transition-colors duration-300 ease-out", isActive && "text-text")}>
                {item.label}
              </span>
            </Link>
          );
        })}
        <button
          type="button"
          onClick={onOpenMenu}
          className="flex min-h-[3.45rem] flex-1 flex-col items-center justify-center gap-0.5 rounded-[1.35rem] px-2 py-1.5 text-text-muted transition-all duration-300 ease-out hover:bg-surface-muted/80 hover:text-text"
          aria-label="Open full navigation menu"
        >
          <Menu className="h-5 w-5 shrink-0" />
          <span className="text-[10px] font-bold leading-tight">Menu</span>
        </button>
      </div>
    </nav>
  );
}

export default BottomNav;
