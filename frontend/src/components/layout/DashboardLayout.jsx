import { useEffect, useRef, useState } from "react";
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
import { tenantService } from "../../services/tenant.service";
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
const tenantNameFallbackRoles = new Set(["admin", "teacher"]);

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
    { label: "Overview", items: [{ label: "Dashboard", to: "/admin/dashboard", icon: Home }, { label: "Create User", to: "/admin/create-user", icon: UserPlus }, { label: "Calendar", to: "/admin/timetable", icon: CalendarDays }] },
    { label: "Academics", items: [{ label: "Students", to: "/admin/students", icon: GraduationCap }, { label: "Teachers", to: "/admin/teachers", icon: Users }, { label: "Parents", to: "/admin/parents", icon: Users }, { label: "Classes", to: "/admin/classes", icon: Library }, { label: "Subjects", to: "/admin/subjects", icon: BookOpen }, { label: "Timetable", to: "/admin/timetable", icon: CalendarDays }, { label: "Attendance", to: "/admin/attendance", icon: CheckSquare }, { label: "Academic Hub", to: "/admin/academic", icon: ClipboardList }] },
    { label: "Communication", items: [{ label: "Notices", to: "/admin/announcements", icon: FileText }, { label: "Messages", to: "/admin/messages", icon: MessageSquare }] },
    { label: "Operations", items: [{ label: "Reports", to: "/admin/reports", icon: BarChart3 }, { label: "Fees", to: "/admin/fees", icon: Receipt }, { label: "Payments", to: "/admin/payments", icon: CreditCard }, { label: "Settings", to: "/admin/settings", icon: Settings }] },
  ],
  teacher: [
    { label: "Subject teaching", items: [{ label: "Dashboard", to: "/teacher/dashboard", icon: Home }, { label: "Teaching Rosters", to: "/teacher/students", icon: GraduationCap }, { label: "Assigned Subjects", to: "/teacher/subjects", icon: BookOpen }, { label: "Score Entry", to: "/teacher/score-entry", icon: BarChart3 }, { label: "Timetable", to: "/teacher/timetable", icon: CalendarDays }, { label: "Assignments", to: "/teacher/assignments", icon: ClipboardList }, { label: "Notices", to: "/teacher/notices", icon: Bell }] },
    { label: "Class teacher duties", items: [{ label: "My Class", to: "/teacher/classes", icon: Library }, { label: "Class Attendance", to: "/teacher/attendance", icon: CheckSquare }, { label: "Class Notices", to: "/teacher/announcements", icon: FileText }] },
  ],
  student: [
    { label: "Learning", items: [{ label: "Dashboard", to: "/student/dashboard", icon: Home }, { label: "Subjects", to: "/student/subjects", icon: BookOpen }, { label: "Parent Linking", to: "/student/parent-linking", icon: Link2 }, { label: "Report Cards", to: "/student/report-cards", icon: FileText }, { label: "Timetable", to: "/student/timetable", icon: CalendarDays }, { label: "Assignments", to: "/student/assignments", icon: ClipboardList }, { label: "Results", to: "/student/results", icon: BarChart3 }, { label: "Notices", to: "/student/notices", icon: FileText }] },
  ],
  parent: [
    { label: "Family", items: [{ label: "Dashboard", to: "/parent/dashboard", icon: Home }, { label: "Student Linking", to: "/parent/student-linking", icon: Link2 }, { label: "Report Cards", to: "/parent/report-cards", icon: FileText }, { label: "Results", to: "/parent/results", icon: BarChart3 }, { label: "Attendance", to: "/parent/attendance", icon: CheckSquare }, { label: "Notices", to: "/parent/notices", icon: FileText }, { label: "Fees", to: "/parent/fees", icon: CreditCard }] },
  ],
  superadmin: [
    { label: "Platform", items: [{ label: "Dashboard", to: "/superadmin/dashboard", icon: Home }, { label: "Tenants", to: "/superadmin/dashboard", icon: Library }, { label: "Announcements", to: "/superadmin/announcements", icon: FileText }, { label: "Verification", to: "/superadmin/verification", icon: Shield }, { label: "Activity", to: "/superadmin/activity", icon: BarChart3 }, { label: "Settings", to: "/superadmin/settings", icon: Settings }] },
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
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function SidebarContent({ role, collapsed, onToggleCollapsed, onNavigate, mobile = false, schoolName }) {
  const location = useLocation();
  const groups = navGroups[role] || navGroups.admin;

  return (
    <div className="flex h-full flex-col">
      <div className={cn("relative flex transition-all duration-300", collapsed ? "flex-col items-center justify-center h-28 gap-3 pt-2" : "h-20 items-center px-4 pr-12")}>
        <Link to="/" className={cn("flex min-w-0 items-center gap-3", collapsed && "justify-center")} onClick={onNavigate}>
          <img src={logoImage} alt="Learnly AI" className={cn("rounded-2xl border border-border bg-surface p-1 shadow-sm", collapsed ? "h-9 w-9" : "h-10 w-10")} />
          {!collapsed && <span className="min-w-0"><span className="block truncate text-lg font-bold leading-tight">Learnly AI</span><span className="block truncate text-xs font-medium text-text-muted">School Management</span></span>}
        </Link>
        {!mobile && <Button type="button" variant="ghost" size="icon" className={cn("hidden h-8 w-8 rounded-lg md:inline-flex transition-all bg-surface-muted hover:bg-border/60", collapsed ? "relative shadow-sm" : "absolute right-3 top-1/2 -translate-y-1/2")} onClick={onToggleCollapsed} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>{collapsed ? <PanelLeftOpen className="h-4 w-4 text-text-soft" /> : <PanelLeftClose className="h-4 w-4 text-text-soft" />}</Button>}
      </div>
      {!collapsed && <div className="mx-4 mb-5 rounded-2xl border border-border/70 bg-surface-muted/35 px-3.5 py-3"><p className="truncate text-[11px] font-semibold uppercase tracking-[0.08em] text-text-faint">Workspace</p><p className="mt-1 truncate text-sm font-semibold text-text">{schoolName || "School workspace"}</p><p className="mt-0.5 truncate text-xs text-text-muted">{roleLabels[role] || "Workspace"}</p></div>}
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 pb-4">
        {groups.map((group) => <div key={group.label}>{!collapsed && <p className="mb-2 px-3 text-[11px] font-bold uppercase tracking-wide text-text-faint">{group.label}</p>}<div className="space-y-1">{group.items.map((item) => { const Icon = item.icon; const isActive = location.pathname === item.to || (item.to !== "/" && location.pathname.startsWith(`${item.to}/`)); return <Link key={`${group.label}-${item.label}`} to={item.to} onClick={onNavigate} title={collapsed ? item.label : undefined} className={cn("group relative nav-item", isActive ? "nav-item-active" : "nav-item-idle", collapsed && "justify-center px-2")}><Icon className="h-4 w-4 shrink-0" />{collapsed && <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2 whitespace-nowrap rounded-lg border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-text shadow-premium opacity-0 transition-opacity duration-150 group-hover:opacity-100">{item.label}</span>}{!collapsed && <><span className="truncate">{item.label}</span>{item.badge && <span className={cn("ml-auto rounded-full px-2 py-0.5 text-[11px] font-bold", isActive ? "bg-white/20 text-white" : "bg-primary-soft text-primary")}>{item.badge}</span>}</>}</Link>; })}</div></div>)}
      </nav>
      {!collapsed && <div className="border-t border-border p-4"><div className="rounded-2xl border border-border bg-surface px-3 py-3 text-sm text-text-soft"><div className="flex items-center gap-3 font-medium"><HelpCircle className="h-4 w-4" />Help & Support</div><p className="mt-2 text-xs text-text-muted">Contact your school administrator for account or school-data issues.</p></div></div>}
    </div>
  );
}

function Topbar({ role, onOpenMobileNav, schoolName }) {
  const navigate = useNavigate();
  const user = authSession.getUser() || {};
  const location = useLocation();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [themeHint, setThemeHint] = useState(() => document.documentElement.dataset.theme || "light");
  const userName = getUserLabel(user);
  const avatarSrc = getUserAvatarSrc(user);
  const canSearchWorkspace = workspaceSearchRoles.has(role);
  const notificationPath = announcementPaths[role] || "/profile";

  useEffect(() => {
    let mounted = true;
    async function loadNotificationPreview() {
      try {
        const response = await announcementService.getFeed({ limit: 5 });
        if (!mounted) return;
        const items = response?.items || [];
        setNotifications(items.slice(0, 5));
        setUnreadCount(items.filter((item) => !item.is_read).length);
      } catch {
        if (!mounted) return;
        setNotifications([]);
        setUnreadCount(0);
      }
    }
    loadNotificationPreview();
    return () => { mounted = false; };
  }, [location.pathname]);

  const handleLogout = () => {
    authService.logout();
    navigate("/login", { replace: true });
  };

  const toggleTheme = () => {
    const nextTheme = themeHint === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem("theme", nextTheme);
    setThemeHint(nextTheme);
  };

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/90 backdrop-blur-xl">
      <div className="mx-auto flex h-[60px] w-full max-w-[1320px] items-center gap-2 px-3 sm:h-[76px] sm:px-5 lg:px-8">
        <Button type="button" variant="ghost" size="icon" className="md:hidden" onClick={onOpenMobileNav} aria-label="Open navigation"><Menu className="h-5 w-5" /></Button>
        <div className="min-w-0 flex-1"><p className="truncate text-[10px] font-bold uppercase tracking-[0.12em] text-text-muted sm:text-xs">Learnly AI</p><p className="truncate text-sm font-semibold text-text sm:text-lg">{schoolName || roleLabels[role] || "Workspace"}</p></div>
        {canSearchWorkspace && <div className="hidden w-full max-w-md md:block"><WorkspaceSearch /></div>}
        <div className="ml-auto flex items-center gap-2">
          <Dropdown align="right" contentClassName="w-80 max-w-[calc(100vw-1.5rem)]" open={notificationsOpen} onOpenChange={setNotificationsOpen} trigger={<button type="button" className="relative inline-flex h-10 w-10 items-center justify-center rounded-full border border-border bg-surface text-text-muted shadow-sm transition hover:bg-surface-muted hover:text-text" aria-label="Open notifications"><Bell className="h-4 w-4" />{unreadCount > 0 && <span className="absolute -right-1 -top-1 rounded-full bg-error px-1.5 py-0.5 text-[10px] font-bold text-white">{unreadCount}</span>}</button>}>
            <div className="space-y-3 p-3"><div className="flex items-center justify-between"><p className="text-sm font-semibold text-text">Notifications</p><Link to={notificationPath} className="text-xs font-semibold text-primary" onClick={() => setNotificationsOpen(false)}>View all</Link></div>{notifications.length > 0 ? notifications.map((item) => <div key={item.id} className="rounded-xl border border-border bg-surface px-3 py-2"><p className="line-clamp-1 text-sm font-semibold text-text">{item.title}</p><p className="mt-1 line-clamp-2 text-xs text-text-muted">{item.message}</p><p className="mt-1 text-[11px] text-text-faint">{notificationTimestamp(item.created_at)}</p></div>) : <p className="rounded-xl border border-dashed border-border px-3 py-4 text-sm text-text-muted">No notifications yet.</p>}</div>
          </Dropdown>
          <button type="button" onClick={toggleTheme} className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-border bg-surface text-text-muted shadow-sm transition hover:bg-surface-muted hover:text-text" aria-label="Toggle theme">{themeHint === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
          <Dropdown align="right" contentClassName="w-64" trigger={<button type="button" className="flex items-center gap-2 rounded-full border border-border bg-surface px-2 py-1.5 shadow-sm transition hover:bg-surface-muted"><Avatar src={avatarSrc} name={userName} size="sm" /><span className="hidden max-w-[9rem] truncate text-sm font-semibold text-text sm:block">{userName}</span><ChevronDown className="h-4 w-4 text-text-muted" /></button>}>
            <div className="p-2"><Link to="/profile" className="block rounded-xl px-3 py-2 text-sm font-medium text-text-soft hover:bg-surface-muted">Profile settings</Link><Link to="/legal" className="block rounded-xl px-3 py-2 text-sm font-medium text-text-soft hover:bg-surface-muted">Legal</Link><button type="button" onClick={handleLogout} className="mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-semibold text-error hover:bg-error-soft"><LogOut className="h-4 w-4" />Logout</button></div>
          </Dropdown>
        </div>
      </div>
    </header>
  );
}

function DashboardLayout({ role: roleProp = "admin", title, description, children }) {
  const user = authSession.getUser() || {};
  const role = getRole(user, roleProp);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [profileMode, setProfileMode] = useState("onboarding");
  const [onboardingState, setOnboardingState] = useState({ loading: true, required: false, status: null });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.localStorage.getItem("sidebarCollapsed") === "true");
  const mainRef = useRef(null);
  const storedSchoolName = resolveSchoolName(user);
  const tenantId = user?.tenant_id;
  const [tenantSchoolName, setTenantSchoolName] = useState("");
  const schoolName = tenantSchoolName || storedSchoolName;

  useEffect(() => {
    window.localStorage.setItem("sidebarCollapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  useEffect(() => {
    let mounted = true;

    if (
      storedSchoolName !== "School workspace" ||
      !tenantId ||
      !tenantNameFallbackRoles.has(role)
    ) {
      return () => {
        mounted = false;
      };
    }

    async function loadTenantName() {
      try {
        const tenant = await tenantService.getTenant(tenantId);
        if (!mounted) return;

        const nextSchoolName = resolveSchoolName(tenant);
        if (nextSchoolName === "School workspace") return;

        const currentUser = authSession.getUser() || {};
        setTenantSchoolName(nextSchoolName);
        authSession.setUser(
          { ...currentUser, school_name: nextSchoolName, tenant },
          { remember: Boolean(window.localStorage.getItem("auth_user")) }
        );
      } catch {
        if (mounted) setTenantSchoolName("");
      }
    }

    loadTenantName();

    return () => {
      mounted = false;
    };
  }, [role, storedSchoolName, tenantId]);

  useEffect(() => {
    let mounted = true;
    async function checkOnboarding() {
      if (!onboardingService.supportsRole(role)) {
        setOnboardingState({ loading: false, required: false, status: null });
        return;
      }

      try {
        const status = await onboardingService.getOnboardingStatus(role);
        if (!mounted) return;

        const required = Boolean(status?.onboarding_required);
        setOnboardingState({ loading: false, required, status: status || null });

        if (required) {
          setProfileMode("onboarding");
          setProfileModalOpen(true);
        }
      } catch {
        if (mounted) setOnboardingState((current) => ({ ...current, loading: false }));
      }
    }
    checkOnboarding();
    return () => { mounted = false; };
  }, [role]);

  const profileCopy = onboardingModalCopy[role] || onboardingModalCopy.teacher;

  const handleProfileStateResolved = ({ completed, status }) => {
    const required = !completed;
    setOnboardingState({ loading: false, required, status: status || null });
    if (!required) setProfileModalOpen(false);
  };

  const handleProfileSaved = (status) => {
    const required = Boolean(status?.onboarding_required);
    setOnboardingState({ loading: false, required, status: status || null });
    if (!required) setProfileModalOpen(false);
  };

  return (
    <div className="min-h-screen bg-background text-text">
      <aside className={cn("fixed inset-y-0 left-0 z-40 hidden border-r border-border bg-surface transition-all duration-300 md:block", sidebarCollapsed ? "w-[5.5rem]" : "w-72")}><SidebarContent role={role} collapsed={sidebarCollapsed} onToggleCollapsed={() => setSidebarCollapsed((value) => !value)} schoolName={schoolName} /></aside>
      {mobileNavOpen && <div className="fixed inset-0 z-50 md:hidden"><div className="absolute inset-0 bg-black/35" onClick={() => setMobileNavOpen(false)} /><aside className="absolute inset-y-0 left-0 w-80 max-w-[85vw] border-r border-border bg-surface shadow-2xl"><div className="flex h-14 items-center justify-end px-4"><Button type="button" variant="ghost" size="icon" onClick={() => setMobileNavOpen(false)} aria-label="Close navigation"><X className="h-5 w-5" /></Button></div><SidebarContent role={role} mobile collapsed={false} onNavigate={() => setMobileNavOpen(false)} schoolName={schoolName} /></aside></div>}
      <div className={cn("min-h-screen transition-[padding] duration-300", sidebarCollapsed ? "md:pl-[5.5rem]" : "md:pl-72")}>
        <Topbar role={role} onOpenMobileNav={() => setMobileNavOpen(true)} schoolName={schoolName} />
        <main ref={mainRef} className="mx-auto flex w-full max-w-[1320px] flex-col gap-5 px-3 pb-28 pt-4 sm:gap-6 sm:px-5 sm:pb-12 sm:pt-6 lg:px-8">
          {(title || description) && <section className="page-header"><div><h1 className="page-title">{title}</h1>{description && <p className="page-description">{description}</p>}</div></section>}
          {children}
        </main>
      </div>
      <BottomNav role={role} onOpenMenu={() => setMobileNavOpen(true)} />
      <Modal open={profileModalOpen} onClose={() => !onboardingState.required && setProfileModalOpen(false)} title={profileMode === "onboarding" ? profileCopy.onboardingTitle : profileCopy.editTitle} description={profileMode === "onboarding" ? profileCopy.onboardingDescription : profileCopy.editDescription} closeOnOverlay={!onboardingState.required} showClose={!onboardingState.required}>
        <ProfileCompletionForm role={role} mode={profileMode} initialStatusData={onboardingState.status} onProfileStateResolved={handleProfileStateResolved} onSaved={handleProfileSaved} />
      </Modal>
      <AiChatLauncher role={role} />
    </div>
  );
}

export default DashboardLayout;
