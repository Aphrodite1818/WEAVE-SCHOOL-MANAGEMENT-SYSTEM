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
  ]
};

function BottomNav({ role, onOpenMenu }) {
  const location = useLocation();
  const items = bottomNavConfig[role] || bottomNavConfig.admin;

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 flex min-h-16 items-center justify-around border-t border-border bg-surface/95 px-2 pb-safe backdrop-blur-xl shadow-[0_-10px_30px_rgba(15,23,42,0.08)] md:hidden"
      aria-label="Primary mobile navigation"
    >
      {items.map((item) => {
        const Icon = item.icon;
        const isActive = location.pathname === item.to || (item.to !== "/" && location.pathname.startsWith(`${item.to}/`));
        return (
          <Link
            key={item.label}
            to={item.to}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "flex min-h-14 flex-1 flex-col items-center justify-center gap-1 rounded-2xl px-2 transition-colors",
              isActive ? "bg-primary-subtle text-primary" : "text-text-muted hover:bg-surface-muted hover:text-text"
            )}
          >
            <Icon className={cn("h-5 w-5", isActive && "fill-primary/20")} />
            <span className="max-w-full truncate text-[10px] font-bold">{item.label}</span>
          </Link>
        );
      })}
      <button
        type="button"
        onClick={onOpenMenu}
        className="flex min-h-14 flex-1 flex-col items-center justify-center gap-1 rounded-2xl px-2 text-text-muted transition-colors hover:bg-surface-muted hover:text-text"
        aria-label="Open full navigation menu"
      >
        <Menu className="h-5 w-5" />
        <span className="text-[10px] font-bold">Menu</span>
      </button>
    </nav>
  );
}

export default BottomNav;
