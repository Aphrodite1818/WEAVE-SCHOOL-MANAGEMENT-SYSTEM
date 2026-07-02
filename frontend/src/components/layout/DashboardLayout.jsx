import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  BarChart3,
  Bell,
  BookOpen,
  CalendarDays,
  CheckSquare,
  ChevronDown,
  ClipboardList,
  CreditCard,
  FileText,
  GraduationCap,
  HelpCircle,
  Home,
  Library,
  Link2,
  LogOut,
  Menu,
  MessageSquare,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Receipt,
  Settings,
  Shield,
  Sun,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import Button from "../ui/Button";
import Avatar from "../ui/Avatar";
import Dropdown from "../ui/Dropdown";
import Modal from "../ui/Modal";
import ProfileCompletionForm from "../shared/ProfileCompletionForm";
import AiChatLauncher from "../ai/AiChatLauncher";
import WorkspaceSearch from "./WorkspaceSearch";
import logoImage from "../../assets/images/favicon.png";
import { authService } from "../../services/auth.service";
import { authSession } from "../../services/api";
import { announcementService } from "../../services/announcementService";
import { onboardingService } from "../../services/onboardingService";
import { cn } from "../../utils/cn";
import { getUserAvatarSrc, schoolName as resolveSchoolName, displayName as resolveDisplayName } from "../../utils/user";
import BottomNav from "./BottomNav";

const roleLabels = {
  admin: "Administrator",
  teacher: "Teacher",
  student: "Student",
  parent: "Parent",
  superadmin: "Platform admin",
};

const workspaceSearchRoles = new Set(["admin", "teacher", "superadmin"]);

const announcementPaths = {
  admin: "/admin/announcements",
  teacher: "/teacher/notices",
  student: "/student/notices",
  parent: "/parent/notices",
  superadmin: "/superadmin/announcements",
};

const onboardingModalCopy = {
  admin: {
    onboardingTitle: "Complete School Profile",
    editTitle: "Edit School Profile",
    onboardingDescription:
      "Finish the school profile fields required for onboarding. School-managed settings stay here, not in a personal profile form.",
    editDescription: "Update your school profile details.",
  },
  teacher: {
    onboardingTitle: "Complete Teacher Profile",
    editTitle: "Edit Teacher Profile",
    onboardingDescription:
      "Complete the teacher profile fields required by the backend before continuing.",
    editDescription: "Update your teacher profile details.",
  },
  parent: {
    onboardingTitle: "Complete Parent Profile",
    editTitle: "Edit Parent Profile",
    onboardingDescription:
      "Complete the parent profile fields required by the backend before continuing.",
    editDescription: "Update your parent profile details.",
  },
  student: {
    onboardingTitle: "Complete Student Profile",
    editTitle: "Edit Student Profile",
    onboardingDescription:
      "Complete the student profile fields required by the backend before continuing.",
    editDescription: "Update your student profile details.",
  },
};

const navGroups = {
  admin: [
    {
      label: "Overview",
      items: [
        { label: "Dashboard", to: "/admin/dashboard", icon: Home },
        { label: "Create User", to: "/admin/create-user", icon: UserPlus },
        { label: "Calendar", to: "/admin/timetable", icon: CalendarDays },
      ],
    },
    {
      label: "Academics",
      items: [
        { label: "Students", to: "/admin/students", icon: GraduationCap },
        { label: "Teachers", to: "/admin/teachers", icon: Users },
        { label: "Parents", to: "/admin/parents", icon: Users },
        { label: "Classes", to: "/admin/classes", icon: Library },
        { label: "Subjects", to: "/admin/subjects", icon: BookOpen },
        { label: "Timetable", to: "/admin/timetable", icon: CalendarDays },
        { label: "Attendance", to: "/admin/attendance", icon: CheckSquare },
        { label: "Academic Hub", to: "/admin/academic", icon: ClipboardList },
      ],
    },
    {
      label: "Communication",
      items: [
        { label: "Notices", to: "/admin/announcements", icon: FileText },
        { label: "Messages", to: "/admin/messages", icon: MessageSquare },
      ],
    },
    {
      label: "Operations",
      items: [
        { label: "Reports", to: "/admin/reports", icon: BarChart3 },
        { label: "Fees", to: "/admin/fees", icon: Receipt },
        { label: "Payments", to: "/admin/payments", icon: CreditCard },
        { label: "Settings", to: "/admin/settings", icon: Settings },
      ],
    },
  ],
  teacher: [
    {
      label: "Teaching",
      items: [
        { label: "Dashboard", to: "/teacher/dashboard", icon: Home },
        { label: "My Classes", to: "/teacher/classes", icon: Library },
        { label: "Students", to: "/teacher/students", icon: GraduationCap },
        { label: "Subjects", to: "/teacher/subjects", icon: BookOpen },
        { label: "Timetable", to: "/teacher/timetable", icon: CalendarDays },
        { label: "Attendance", to: "/teacher/attendance", icon: CheckSquare },
        { label: "Assignments", to: "/teacher/assignments", icon: ClipboardList },
        { label: "Notices", to: "/teacher/notices", icon: Bell },
        { label: "Class Notices", to: "/teacher/announcements", icon: FileText },
        { label: "Results", to: "/teacher/results", icon: BarChart3 },
      ],
    },
  ],
  student: [
    {
      label: "Learning",
      items: [
        { label: "Dashboard", to: "/student/dashboard", icon: Home },
        { label: "Subjects", to: "/student/subjects", icon: BookOpen },
        { label: "Parent Linking", to: "/student/parent-linking", icon: Link2 },
        { label: "Report Cards", to: "/student/report-cards", icon: FileText },
        { label: "Timetable", to: "/student/timetable", icon: CalendarDays },
        { label: "Assignments", to: "/student/assignments", icon: ClipboardList },
        { label: "Results", to: "/student/results", icon: BarChart3 },
        { label: "Notices", to: "/student/notices", icon: FileText },
      ],
    },
  ],
  parent: [
    {
      label: "Family",
      items: [
        { label: "Dashboard", to: "/parent/dashboard", icon: Home },
        { label: "Student Linking", to: "/parent/student-linking", icon: Link2 },
        { label: "Report Cards", to: "/parent/report-cards", icon: FileText },
        { label: "Results", to: "/parent/results", icon: BarChart3 },
        { label: "Attendance", to: "/parent/attendance", icon: CheckSquare },
        { label: "Notices", to: "/parent/notices", icon: FileText },
        { label: "Fees", to: "/parent/fees", icon: CreditCard },
      ],
    },
  ],
  superadmin: [
    {
      label: "Platform",
      items: [
        { label: "Dashboard", to: "/superadmin/dashboard", icon: Home },
        { label: "Tenants", to: "/superadmin/dashboard", icon: Library },
        { label: "Announcements", to: "/superadmin/announcements", icon: FileText },
        { label: "Verification", to: "/superadmin/verification", icon: Shield },
        { label: "Activity", to: "/superadmin/activity", icon: BarChart3 },
        { label: "Settings", to: "/superadmin/settings", icon: Settings },
      ],
    },
  ],
};

function getUserLabel(user) {
  return resolveDisplayName(user);
}

function getRole(user, fallback) {
  return String(user?.role || authSession.getRole() || fallback || "admin").toLowerCase();
}

function notificationTimestamp(value) {
  if (!value) return "";
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function SidebarContent({ role, collapsed, onToggleCollapsed, onNavigate, mobile = false, schoolName }) {
  const location = useLocation();
  const groups = navGroups[role] || navGroups.admin;

  return (
    <div className="flex h-full flex-col">
      <div className={cn("relative flex transition-all duration-300", collapsed ? "flex-col items-center justify-center h-28 gap-3 pt-2" : "h-20 items-center px-4 pr-12")}>
        <Link to="/" className={cn("flex min-w-0 items-center gap-3", collapsed && "justify-center")} onClick={onNavigate}>
          <img
            src={logoImage}
            alt="Learnly AI"
            className={cn("rounded-2xl border border-border bg-surface p-1 shadow-sm", collapsed ? "h-9 w-9" : "h-10 w-10")}
          />
          {!collapsed && (
            <span className="min-w-0">
              <span className="block truncate text-lg font-bold leading-tight">Learnly AI</span>
              <span className="block truncate text-xs font-medium text-text-muted">School Management</span>
            </span>
          )}
        </Link>
        {!mobile && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={cn("hidden h-8 w-8 rounded-lg md:inline-flex transition-all bg-surface-muted hover:bg-border/60", collapsed ? "relative shadow-sm" : "absolute right-3 top-1/2 -translate-y-1/2")}
            onClick={onToggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4 text-text-soft" /> : <PanelLeftClose className="h-4 w-4 text-text-soft" />}
          </Button>
        )}
      </div>

      {!collapsed && (
        <div className="mx-4 mb-5 rounded-2xl border border-border/70 bg-surface-muted/35 px-3.5 py-3">
          <p className="truncate text-[11px] font-semibold uppercase tracking-[0.08em] text-text-faint">
            Workspace
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-text">
            {schoolName || "School workspace"}
          </p>
          <p className="mt-0.5 truncate text-xs text-text-muted">{roleLabels[role] || "Workspace"}</p>
        </div>
      )}

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 pb-4">
        {groups.map((group) => (
          <div key={group.label}>
            {!collapsed && (
              <p className="mb-2 px-3 text-[11px] font-bold uppercase tracking-wide text-text-faint">
                {group.label}
              </p>
            )}
            <div className="space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive =
                  location.pathname === item.to ||
                  (item.to !== "/" && location.pathname.startsWith(`${item.to}/`));

                return (
                  <Link
                    key={`${group.label}-${item.label}`}
                    to={item.to}
                    onClick={onNavigate}
                    title={collapsed ? item.label : undefined}
                    className={cn(
                      "group relative nav-item",
                      isActive ? "nav-item-active" : "nav-item-idle",
                      collapsed && "justify-center px-2"
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {collapsed && (
                      <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2 whitespace-nowrap rounded-lg border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-text shadow-premium opacity-0 transition-opacity duration-150 group-hover:opacity-100">
                        {item.label}
                      </span>
                    )}
                    {!collapsed && (
                      <>
                        <span className="truncate">{item.label}</span>
                        {item.badge && (
                          <span className={cn("ml-auto rounded-full px-2 py-0.5 text-[11px] font-bold", isActive ? "bg-white/20 text-white" : "bg-primary-soft text-primary")}>
                            {item.badge}
                          </span>
                        )}
                      </>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {!collapsed && (
        <div className="border-t border-border p-4">
          <div className="rounded-2xl border border-border bg-surface px-3 py-3 text-sm text-text-soft">
            <div className="flex items-center gap-3 font-medium">
              <HelpCircle className="h-4 w-4" />
              Help & Support
            </div>
            <p className="mt-2 text-xs text-text-muted">
              Contact your school administrator for account or school-data issues.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function Topbar({ role, onOpenMobileNav, schoolName }) {
  const navigate = useNavigate();
  const user = authSession.getUser();
  const userName = getUserLabel(user);
  const avatarSrc = getUserAvatarSrc(user);
  const notificationPath = announcementPaths[role] || announcementPaths.admin;
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationError, setNotificationError] = useState("");
  const [themeHint, setThemeHint] = useState(() => {
    if (typeof window === "undefined") return "light";
    return (
      localStorage.getItem("theme") ||
      (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    );
  });
  const hasUnreadNotifications = unreadCount > 0;

  useEffect(() => {
    let mounted = true;

    async function loadNotifications() {
      if (!authSession.getToken()) return;

      try {
        const response = await announcementService.getFeed(
          role === "teacher" ? { limit: 5, delivery_kind: "notice" } : { limit: 5 }
        );
        if (!mounted) return;
        const items = response?.items || [];
        setNotifications(items);
        setUnreadCount(response?.unread_count ?? items.filter((item) => !item.is_read).length);
        setNotificationError("");
      } catch {
        if (!mounted) return;
        setNotifications([]);
        setUnreadCount(0);
        setNotificationError("Unable to load notifications right now.");
      }
    }

    loadNotifications();
    const intervalId = window.setInterval(loadNotifications, 60000);

    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, [role]);

  const toggleTheme = () => {
    setThemeHint((current) => {
      const nextTheme = current === "light" ? "dark" : "light";
      document.documentElement.dataset.theme = nextTheme;
      localStorage.setItem("theme", nextTheme);
      return nextTheme;
    });
  };

  useEffect(() => {
    document.documentElement.dataset.theme = themeHint;
  }, [themeHint]);

  const handleLogout = () => {
    authService.logout();
    navigate("/login", { replace: true });
  };

  const openNotification = async (item) => {
    if (!item?.is_read) {
      setNotifications((current) =>
        current.map((notification) =>
          notification.id === item.id ? { ...notification, is_read: true } : notification
        )
      );
      setUnreadCount((current) => Math.max(current - 1, 0));
      try {
        await announcementService.markRead(item.id);
      } catch {
        // The next polling cycle will reconcile read state with the backend.
      }
    }
    navigate(notificationPath);
  };

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/90 backdrop-blur-xl">
      <div className="flex min-h-16 items-center gap-3 px-4 sm:min-h-20 sm:px-6 lg:px-8">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={onOpenMobileNav}
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </Button>

        <div className="min-w-0 md:hidden">
          <p className="truncate text-xs font-semibold uppercase tracking-wide text-text-muted">Learnly AI</p>
          <p className="truncate text-sm font-semibold text-text">{schoolName || "School workspace"}</p>
        </div>

        {workspaceSearchRoles.has(role) ? (
          <WorkspaceSearch role={role} />
        ) : (
          <div className="hidden md:flex items-center gap-3 rounded-2xl bg-surface-muted/30 px-4 py-2 border border-border/50">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary-soft text-primary">
              <CalendarDays className="h-4 w-4" />
            </span>
            <div className="flex flex-col">
              <span className="text-[10px] font-bold uppercase tracking-wider text-text-faint">Today's Date</span>
              <span className="text-sm font-semibold text-text">
                {new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'long', day: 'numeric', year: 'numeric' })}
              </span>
            </div>
          </div>
        )}

        <div className="ml-auto flex items-end gap-2">


          <Dropdown
            trigger={
              <Button
                type="button"
                variant={hasUnreadNotifications ? "primary" : "outline"}
                size="icon"
                className={cn("relative h-12 w-12 rounded-2xl", hasUnreadNotifications && "shadow-[0_0_0_4px_rgba(37,99,235,0.16)]")}
                aria-label={hasUnreadNotifications ? `${unreadCount} unread notifications` : "No unread notifications"}
              >
                <Bell className="h-4 w-4" />
                {hasUnreadNotifications && (
                  <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full border-2 border-background bg-error px-1 text-[10px] font-bold leading-none text-white">
                    {unreadCount > 9 ? "9+" : unreadCount}
                  </span>
                )}
              </Button>
            }
          >
            <div className="w-80 max-w-[calc(100vw-2rem)] px-2 py-1">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">Notifications</p>
                  <p className="text-xs text-text-muted">
                    {hasUnreadNotifications ? `${unreadCount} unread announcement${unreadCount === 1 ? "" : "s"}` : "You are all caught up."}
                  </p>
                </div>
                <Link to={notificationPath} className="text-xs font-semibold text-primary hover:underline">
                  View all
                </Link>
              </div>
            </div>
            <div className="mt-2 space-y-2">
              {notificationError && (
                <p className="rounded-xl bg-error-soft px-3 py-3 text-sm text-error">
                  {notificationError}
                </p>
              )}
              {!notificationError && notifications.length === 0 && (
                <p className="rounded-xl bg-surface-muted px-3 py-3 text-sm text-text-muted">
                  No announcements have been sent to you yet.
                </p>
              )}
              {!notificationError && notifications.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => openNotification(item)}
                  className={cn(
                    "block w-full rounded-xl border px-3 py-3 text-left transition hover:border-primary/40 hover:bg-primary-subtle",
                    item.is_read ? "border-border bg-surface text-text-soft" : "border-primary/40 bg-primary-subtle text-text"
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="line-clamp-1 text-sm font-semibold">{item.title}</p>
                    {!item.is_read && <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" />}
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-text-muted">{item.body}</p>
                  <p className="mt-2 text-[11px] font-semibold uppercase text-text-faint">
                    {[item.priority, item.category, notificationTimestamp(item.publish_at || item.created_at)].filter(Boolean).join(" | ")}
                  </p>
                </button>
              ))}
            </div>
          </Dropdown>

          <Dropdown
            trigger={
              <button type="button" className="flex h-12 min-h-12 items-center gap-2 rounded-2xl border border-border bg-surface p-1.5 pr-2 shadow-sm transition hover:bg-surface-muted sm:gap-3 sm:pr-3" aria-label="Open account menu">
                <Avatar name={userName} src={avatarSrc} user={user} />
                <span className="hidden min-w-0 text-left xl:block">
                  <span className="block max-w-32 truncate text-sm font-semibold">{userName}</span>
                  <span className="block text-xs text-text-muted">{roleLabels[role] || "User"}</span>
                </span>
                <ChevronDown className="hidden h-4 w-4 text-text-faint sm:block" />
              </button>
            }
          >
            <div className="flex items-center gap-3 px-3 py-2">
              <Avatar name={userName} src={avatarSrc} user={user} size="lg" />
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{userName}</p>
                <p className="truncate text-xs text-text-muted">{roleLabels[role] || "User"}</p>
              </div>
            </div>
            <div className="my-2 border-t border-border" />
            <Link to="/profile" className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-text-soft hover:bg-surface-muted">
              <Settings className="h-4 w-4" />
              Profile page
            </Link>
            <Link to="/legal" className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-text-soft hover:bg-surface-muted">
              <Shield className="h-4 w-4" />
              Legal
            </Link>
            <button
              type="button"
              onClick={toggleTheme}
              className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-medium text-text-soft hover:bg-surface-muted"
            >
              {themeHint === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
              {themeHint === "light" ? "Switch to dark mode" : "Switch to light mode"}
            </button>
            <button type="button" onClick={handleLogout} className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-error hover:bg-error-soft">
              <LogOut className="h-4 w-4" />
              Log out
            </button>
          </Dropdown>
        </div>
      </div>
    </header>
  );
}

function DashboardLayout({
  role: roleProp,
  title = "Dashboard",
  description,
  actions,
  children,
  onboardingModalEnabled = true,
}) {
  const user = authSession.getUser();
  const role = getRole(user, roleProp);
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("dashboard-sidebar-collapsed") === "true";
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileUser, setProfileUser] = useState(user);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [onboardingStatusData, setOnboardingStatusData] = useState(null);
  const [isLoadingOnboardingState, setIsLoadingOnboardingState] = useState(Boolean(authSession.getToken()));
  const onboardingAutoOpenKeyRef = useRef("");

  const pageTitle = useMemo(() => title || `${roleLabels[role] || "Workspace"} Dashboard`, [role, title]);
  const needsOnboarding =
    onboardingModalEnabled && Boolean(onboardingStatusData?.onboarding_required);
  const onboardingAutoOpenKey = `${role}:${profileUser?.id || "anonymous"}`;
  const schoolName = resolveSchoolName({
    school_name:
      onboardingStatusData?.current_values?.school_name ||
      profileUser?.tenant?.school_name,
  });

  const modalCopy = onboardingModalCopy[role] || onboardingModalCopy.teacher;

  const closeProfileModal = useCallback(() => {
    setProfileModalOpen(false);
  }, []);
  const handleProfileSaved = useCallback((nextStatus, nextUser) => {
    setOnboardingStatusData(nextStatus || null);
    setProfileUser(nextUser || authSession.getUser());
    setProfileModalOpen(false);
  }, []);
  const handleProfileStateResolved = useCallback((state) => {
    setIsLoadingOnboardingState(false);
    if (state?.status) setOnboardingStatusData(state.status);
    if (state?.user) setProfileUser(state.user);
  }, []);

  useEffect(() => {
    let mounted = true;

    async function hydrateOnboardingState() {
      if (
        !onboardingModalEnabled ||
        !authSession.getToken() ||
        !onboardingService.supportsRole(role)
      ) {
        setIsLoadingOnboardingState(false);
        return;
      }

      try {
        const nextStatus = await onboardingService.getOnboardingStatus(role);
        if (!mounted) return;

        setOnboardingStatusData(nextStatus);
        setProfileUser(authSession.getUser());
      } catch {
        if (!mounted) return;
      } finally {
        if (mounted) setIsLoadingOnboardingState(false);
      }
    }

    hydrateOnboardingState();

    return () => {
      mounted = false;
    };
  }, [onboardingModalEnabled, role]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("dashboard-sidebar-collapsed", String(collapsed));
  }, [collapsed]);

  useEffect(() => {
    if (isLoadingOnboardingState || !needsOnboarding) return;
    if (onboardingAutoOpenKeyRef.current === onboardingAutoOpenKey) return;

    onboardingAutoOpenKeyRef.current = onboardingAutoOpenKey;
    const timeoutId = window.setTimeout(() => setProfileModalOpen(true), 0);
    return () => window.clearTimeout(timeoutId);
  }, [isLoadingOnboardingState, needsOnboarding, onboardingAutoOpenKey]);

  return (
    <div className="min-h-screen bg-background text-text">
      <a
        href="#dashboard-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-xl focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white"
      >
        Skip to content
      </a>
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden border-r border-border bg-surface transition-[width] duration-[180ms] ease-in-out md:block",
          collapsed ? "w-14" : "w-[220px]"
        )}
      >
        <SidebarContent
          role={role}
          collapsed={collapsed}
          onToggleCollapsed={() => setCollapsed((current) => !current)}
          schoolName={schoolName}
        />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-sm transition-opacity duration-300" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-[86vw] max-w-80 flex-col border-r border-border bg-surface shadow-premium">
            <div className="flex min-h-16 items-center justify-end border-b border-border px-3">
              <Button type="button" variant="ghost" size="icon" className="relative z-10" onClick={() => setMobileOpen(false)} aria-label="Close navigation">
                <X className="h-5 w-5" />
              </Button>
            </div>
            <div className="min-h-0 flex-1">
              <SidebarContent role={role} collapsed={false} mobile onNavigate={() => setMobileOpen(false)} schoolName={schoolName} />
            </div>
          </aside>
        </div>
      )}

      <div className={cn("min-h-screen transition-[padding] duration-[180ms] ease-in-out", collapsed ? "md:pl-14" : "md:pl-[220px]")}>
        <Topbar
          role={role}
          onOpenMobileNav={() => setMobileOpen(true)}
          schoolName={schoolName}
        />

        <main id="dashboard-content" className="px-2 py-4 pb-24 sm:px-5 sm:py-5 md:px-6 md:py-6 md:pb-6 lg:px-8">
          <div className="mx-auto flex w-full max-w-[1320px] flex-col section-gap">
            <div className="flex flex-col gap-3 rounded-[1.6rem] border border-border/60 bg-surface/65 p-4 shadow-sm backdrop-blur-sm sm:gap-4 sm:p-5 lg:flex-row lg:items-start lg:justify-between lg:p-6">
              <div className="min-w-0">
                <h1 className="dashboard-title">
                  {pageTitle}
                </h1>
                {description && (
                  <p className="dashboard-subtitle">
                    {description}
                  </p>
                )}
              </div>
              {actions && (
                <div className="flex w-full flex-wrap gap-2 lg:w-auto lg:justify-end [&_.btn-base]:min-h-10 [&_a]:flex-1 sm:[&_a]:flex-none">
                  {actions}
                </div>
              )}
            </div>
            {children}
          </div>
        </main>
      </div>
      <BottomNav role={role} onOpenMenu={() => setMobileOpen(true)} />
      <AiChatLauncher />
      {onboardingModalEnabled && (
        <Modal
          open={profileModalOpen}
          title={needsOnboarding ? modalCopy.onboardingTitle : modalCopy.editTitle}
          description={
            needsOnboarding
              ? modalCopy.onboardingDescription
              : modalCopy.editDescription
          }
          onClose={needsOnboarding ? null : closeProfileModal}
        >
          <ProfileCompletionForm
            role={role}
            submitLabel="Save profile"
            initialStatusData={onboardingStatusData}
            onSaved={handleProfileSaved}
            onProfileStateResolved={handleProfileStateResolved}
          />
        </Modal>
      )}
    </div>
  );
}

export default DashboardLayout;
