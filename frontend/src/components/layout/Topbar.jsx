import { Bell, Building2, ChevronDown, CreditCard, FileText, LogOut, Menu, Moon, Settings, Sun, Trash2, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { formatPlanName } from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { NOTIFICATIONS_CHANGED_EVENT, emitNotificationsChanged, notificationService } from "../../services/communicationService";
import { authSession } from "../../services/api";
import { authService } from "../../services/auth.service";
import { cn } from "../../utils/cn";
import {
  applyAccessibilityPreferences,
  getSavedAccessibilityPreferences,
  saveAccessibilityPreferences,
} from "../../utils/accessibilityPreferences";
import {
  displayName as resolveDisplayName,
  getUserAvatarSrc,
} from "../../utils/user";
import WeaveIcon from "../brand/WeaveIcon";
import Avatar from "../ui/Avatar";
import Dropdown from "../ui/Dropdown";
import WorkspaceSearch from "./WorkspaceSearch";
import { inboxPaths, roleLabels, workspaceSearchRoles } from "./navConfig";

const headerIconButtonClass =
  "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface/90 text-text-muted shadow-[0_10px_24px_rgba(15,23,42,0.08)] transition hover:bg-surface-muted hover:text-text sm:h-10 sm:w-10";

function notificationTimestamp(value) {
  if (!value) return "";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function getUserLabel(user) {
  return resolveDisplayName(user);
}

const roleSettingsPaths = {
  admin: "/admin/settings",
  teacher: "/teacher/settings",
  student: "/student/settings",
  parent: "/parent/settings",
  superadmin: "/superadmin/settings",
};

const schoolSwitchPaths = {
  teacher: "/teacher/schools",
  parent: "/parent/schools",
};

export default function Topbar({
  role,
  onOpenMobileNav,
  schoolName,
  schoolLogoUrl = "",
}) {
  const navigate = useNavigate();
  const user = authSession.getUser() || {};
  const actorType = String(user?.actor_type || "").toLowerCase();
  const isAccountScope =
    ["parent_account", "teacher_account"].includes(actorType) &&
    !user?.tenant_id;
  const { isTenantAdmin, planCode } = useSubscription();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationsError, setNotificationsError] = useState("");
  const [notificationRefreshKey, setNotificationRefreshKey] = useState(0);
  const [failedSchoolLogoUrl, setFailedSchoolLogoUrl] = useState("");
  const [themeHint, setThemeHint] = useState(() =>
    typeof document === "undefined"
      ? "light"
      : document.documentElement.dataset.theme || "light"
  );
  const userName = getUserLabel(user);
  const avatarSrc = getUserAvatarSrc(user);
  const canSearchWorkspace = !isAccountScope && workspaceSearchRoles.has(role);
  const isSuperadmin = role === "superadmin";
  const notificationPath = isAccountScope
    ? schoolSwitchPaths[role] || "/profile"
    : inboxPaths[role] || "/profile";
  const showPlanBadge = role === "admin" && isTenantAdmin;
  const settingsPath = isAccountScope
    ? "/profile"
    : roleSettingsPaths[role] || "/profile";
  const schoolSwitchPath = schoolSwitchPaths[role] || null;
  const resolvedSchoolLogoUrl =
    schoolLogoUrl ||
    user?.tenant_logo_url ||
    user?.tenant?.logo_url ||
    "";
  const hasSchoolLogo =
    Boolean(resolvedSchoolLogoUrl) &&
    failedSchoolLogoUrl !== resolvedSchoolLogoUrl &&
    !isAccountScope;

  useEffect(() => {
    let mounted = true;

    if (isAccountScope) {
      setNotifications([]);
      setUnreadCount(0);
      setNotificationsError("");
      setNotificationsLoading(false);
      return () => {
        mounted = false;
      };
    }

    async function loadNotificationPreview() {
      setNotificationsLoading(true);
      setNotificationsError("");
      try {
        const response = await notificationService.list({ limit: 5 });
        if (!mounted) return;
        const items = response?.items || [];
        setNotifications(items.slice(0, 5));
        setUnreadCount(Number(response?.unread_count || 0));
      } catch {
        if (!mounted) return;
        setNotifications([]);
        setUnreadCount(0);
        setNotificationsError("Could not load notifications.");
      } finally {
        if (mounted) setNotificationsLoading(false);
      }
    }

    loadNotificationPreview();

    return () => {
      mounted = false;
    };
  }, [isAccountScope, isSuperadmin, notificationRefreshKey, role]);

  useEffect(() => {
    if (isAccountScope) return undefined;

    const refreshNotifications = () => setNotificationRefreshKey((value) => value + 1);
    window.addEventListener(NOTIFICATIONS_CHANGED_EVENT, refreshNotifications);
    window.addEventListener("focus", refreshNotifications);

    return () => {
      window.removeEventListener(NOTIFICATIONS_CHANGED_EVENT, refreshNotifications);
      window.removeEventListener("focus", refreshNotifications);
    };
  }, [isAccountScope]);

  useEffect(() => {
    const syncThemeHint = () => {
      setThemeHint(document.documentElement.dataset.theme || "light");
    };

    window.addEventListener("weave:accessibility-preferences-changed", syncThemeHint);
    return () => window.removeEventListener("weave:accessibility-preferences-changed", syncThemeHint);
  }, []);

  const handleLogout = async () => {
    setAccountMenuOpen(false);
    await authService.logout();
    navigate("/login", { replace: true });
  };

  const closeAccountMenu = () => setAccountMenuOpen(false);

  const toggleTheme = () => {
    const nextTheme = themeHint === "light" ? "dark" : "light";
    const preferences = { ...getSavedAccessibilityPreferences(), theme: nextTheme };
    applyAccessibilityPreferences(preferences);
    saveAccessibilityPreferences(preferences);
    setThemeHint(nextTheme);
  };

  const deleteReadNotification = async (id) => {
    try {
      await notificationService.dismiss(id);
      setNotifications((current) => current.filter((item) => item.id !== id));
      setNotificationRefreshKey((value) => value + 1);
      emitNotificationsChanged();
    } catch {
      setNotificationsError("Could not delete notification.");
    }
  };

  return (
    <header className="dashboard-topbar sticky top-0 z-50 shrink-0 border-b border-border bg-surface pt-[env(safe-area-inset-top)]">
      <div className="mx-auto flex h-[3.75rem] w-full max-w-[1320px] items-center gap-1.5 px-2 sm:gap-2 sm:px-5 md:h-16 md:px-4 lg:px-5">
        <button
          type="button"
          className={cn(headerIconButtonClass, "md:hidden")}
          onClick={onOpenMobileNav}
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <div className="flex min-w-0 items-center gap-2 sm:hidden">
            {hasSchoolLogo ? (
              <img
                src={resolvedSchoolLogoUrl}
                alt={`${schoolName || "School"} logo`}
                className="h-8 w-8 shrink-0 rounded-lg border border-border/70 bg-surface object-contain p-0.5 shadow-sm"
                onError={() => setFailedSchoolLogoUrl(resolvedSchoolLogoUrl)}
              />
            ) : null}
            <p className="truncate text-base font-bold text-text">
              {isAccountScope ? "Your schools" : schoolName || roleLabels[role] || "Workspace"}
            </p>
          </div>
          {hasSchoolLogo ? (
            <img
              src={resolvedSchoolLogoUrl}
              alt={`${schoolName || "School"} logo`}
              className="hidden h-9 w-9 shrink-0 rounded-xl border border-border/70 bg-surface object-contain p-1 shadow-sm sm:block"
              onError={() => setFailedSchoolLogoUrl(resolvedSchoolLogoUrl)}
            />
          ) : (
            <WeaveIcon className="hidden h-8 w-8 shrink-0 sm:block" decorative />
          )}
          <div className="hidden min-w-0 sm:block">
            <p className="brand-wordmark truncate text-sm font-bold sm:text-lg">
              {hasSchoolLogo ? schoolName || "School workspace" : "Weave"}
            </p>
          </div>
        </div>

        {canSearchWorkspace && (
          <div className="hidden w-full max-w-md md:block">
            <WorkspaceSearch role={role} />
          </div>
        )}

        {role === "superadmin" && (
          <div className="hidden w-full max-w-md items-center justify-center md:flex">
             <div className="flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-primary shadow-sm">
                <div className="h-2 w-2 animate-pulse rounded-full bg-primary"></div>
                Platform Operations
             </div>
          </div>
        )}

        <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
          {!isAccountScope ? (
            <Dropdown
              align="right"
              className="notification-dropdown-panel w-80 max-w-[calc(100vw-1rem)]"
              open={notificationsOpen}
              onOpenChange={setNotificationsOpen}
              trigger={
                <button type="button" className={cn(headerIconButtonClass, "relative")} aria-label="Open notifications">
                  <Bell className="h-4 w-4" />
                  {unreadCount > 0 && (
                    <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-error px-1 text-[10px] font-bold leading-none text-white">{unreadCount}</span>
                  )}
                </button>
              }
            >
              <div className="space-y-3 p-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-text">Notifications</p>
                  <Link to={notificationPath} className="text-xs font-semibold text-primary" onClick={() => setNotificationsOpen(false)}>View all</Link>
                </div>
                {notificationsLoading ? (
                  <p className="rounded-xl border border-border px-3 py-4 text-sm text-text-muted">Loading notifications...</p>
                ) : notificationsError ? (
                  <div className="rounded-xl border border-error/30 bg-error-soft px-3 py-4 text-sm text-error">
                    <p>{notificationsError}</p>
                    <button type="button" className="mt-2 text-xs font-semibold underline" onClick={() => setNotificationRefreshKey((value) => value + 1)}>Retry</button>
                  </div>
                ) : notifications.length > 0 ? (
                  notifications.map((item) => (
                    <div key={item.id} className="rounded-xl border border-border bg-surface px-3 py-2">
                      <div className="flex items-start gap-2">
                        <p className="min-w-0 flex-1 line-clamp-1 text-sm font-semibold text-text">{item.title}</p>
                        {item.status !== "unread" ? (
                          <button
                            type="button"
                            className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-text-faint transition hover:bg-error-soft hover:text-error"
                            aria-label="Delete notification"
                            onClick={() => deleteReadNotification(item.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        ) : null}
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-text-muted">{item.preview}</p>
                      <p className="mt-1 text-[11px] text-text-faint">{notificationTimestamp(item.delivered_at)}</p>
                    </div>
                  ))
                ) : (
                  <p className="rounded-xl border border-dashed border-border px-3 py-4 text-sm text-text-muted">No notifications yet.</p>
                )}
              </div>
            </Dropdown>
          ) : null}

          <button
            type="button"
            onClick={toggleTheme}
            className={headerIconButtonClass}
            aria-label="Toggle theme"
          >
            {themeHint === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>

          <Dropdown
            align="right"
            className="w-72 max-w-[calc(100vw-1rem)]"
            open={accountMenuOpen}
            onOpenChange={setAccountMenuOpen}
            trigger={
              <button type="button" className="flex h-10 items-center gap-2 rounded-full bg-surface/90 px-2 py-1 text-text-muted shadow-[0_10px_24px_rgba(15,23,42,0.08)] transition hover:bg-surface-muted hover:text-text">
                <Avatar src={avatarSrc} name={userName} size="sm" />
                <span className="hidden max-w-[10rem] flex-col items-start leading-tight sm:flex">
                  <span className="max-w-full truncate text-sm font-semibold text-text">{userName}</span>
                  {showPlanBadge ? <span className="mt-0.5 text-[10px] font-semibold uppercase tracking-wide text-text-muted">{formatPlanName(planCode)}</span> : null}
                </span>
                <ChevronDown className="h-4 w-4 text-text-muted" />
              </button>
            }
          >
            <div className="p-2">
              <div className="mb-2 rounded-2xl border border-border/70 bg-surface-muted/35 px-3 py-3">
                <div className="flex items-center gap-3">
                  <Avatar src={avatarSrc} name={userName} size="sm" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-text">{userName}</p>
                    <p className="truncate text-xs text-text-muted">{roleLabels[role] || "Workspace"}</p>
                  </div>
                </div>
                {showPlanBadge ? <p className="mt-3 text-xs text-text-muted">{formatPlanName(planCode)}</p> : null}
              </div>
              <div className="mb-2 grid gap-2">
                {schoolSwitchPath ? (
                  <Link
                    to={schoolSwitchPath}
                    onClick={closeAccountMenu}
                    className="flex min-h-11 items-center gap-3 rounded-2xl border border-border/70 bg-surface px-3 py-2 text-sm font-semibold text-text transition hover:border-primary/30 hover:bg-primary-subtle/35"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                      <Building2 className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1 truncate">Switch school</span>
                  </Link>
                ) : null}
                <Link
                  to={settingsPath}
                  onClick={closeAccountMenu}
                  className="flex min-h-11 items-center gap-3 rounded-2xl border border-border/70 bg-surface px-3 py-2 text-sm font-semibold text-text transition hover:border-primary/30 hover:bg-primary-subtle/35"
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                    <Settings className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1 truncate">Settings</span>
                </Link>
                {showPlanBadge ? (
                  <Link
                    to="/admin/billing"
                    onClick={closeAccountMenu}
                    className="flex min-h-11 items-center gap-3 rounded-2xl border border-border/70 bg-surface px-3 py-2 text-sm font-semibold text-text transition hover:border-primary/30 hover:bg-primary-subtle/35"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                      <CreditCard className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1 truncate">Upgrade</span>
                  </Link>
                ) : null}
                <Link
                  to="/profile"
                  onClick={closeAccountMenu}
                  className="flex min-h-11 items-center gap-3 rounded-2xl border border-border/70 bg-surface px-3 py-2 text-sm font-semibold text-text transition hover:border-primary/30 hover:bg-primary-subtle/35"
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-surface-muted text-text-soft">
                    <UserRound className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1 truncate">Profile</span>
                </Link>
                <Link
                  to="/legal"
                  onClick={closeAccountMenu}
                  className="flex min-h-11 items-center gap-3 rounded-2xl border border-border/70 bg-surface px-3 py-2 text-sm font-semibold text-text transition hover:border-primary/30 hover:bg-primary-subtle/35"
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-surface-muted text-text-soft">
                    <FileText className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1 truncate">Legal</span>
                </Link>
              </div>
              <button type="button" onClick={handleLogout} className="mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-semibold text-error hover:bg-error-soft">
                <LogOut className="h-4 w-4" /> Logout
              </button>
            </div>
          </Dropdown>
        </div>
      </div>
      {canSearchWorkspace ? (
        <div className="border-t border-border/60 px-3 py-2 md:hidden">
          <WorkspaceSearch role={role} />
        </div>
      ) : null}
    </header>
  );
}
