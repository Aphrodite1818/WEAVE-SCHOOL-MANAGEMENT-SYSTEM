import { Bell, ChevronDown, LogOut, Menu, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { formatPlanName } from "../../features/subscriptions/subscriptionConfig";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { announcementService } from "../../services/announcementService";
import { authSession } from "../../services/api";
import { authService } from "../../services/auth.service";
import { cn } from "../../utils/cn";
import {
  displayName as resolveDisplayName,
  getUserAvatarSrc,
} from "../../utils/user";
import Avatar from "../ui/Avatar";
import Dropdown from "../ui/Dropdown";
import WorkspaceSearch from "./WorkspaceSearch";
import { announcementPaths, roleLabels, workspaceSearchRoles } from "./navConfig";

const headerIconButtonClass =
  "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-header-border/60 bg-header-surface/90 text-header-muted shadow-[0_10px_24px_rgba(15,23,42,0.12)] transition hover:bg-header-surface-hover hover:text-header-text sm:h-10 sm:w-10";

function notificationTimestamp(value) {
  if (!value) return "";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function getUserLabel(user) {
  return resolveDisplayName(user);
}

export default function Topbar({ role, onOpenMobileNav, schoolName }) {
  const navigate = useNavigate();
  const user = authSession.getUser() || {};
  const { isTenantAdmin, planCode, statusMeta } = useSubscription();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [themeHint, setThemeHint] = useState(() =>
    typeof document === "undefined"
      ? "light"
      : document.documentElement.dataset.theme || "light"
  );
  const userName = getUserLabel(user);
  const avatarSrc = getUserAvatarSrc(user);
  const canSearchWorkspace = workspaceSearchRoles.has(role);
  const notificationPath = announcementPaths[role] || "/profile";
  const showPlanBadge = role === "admin" && isTenantAdmin;

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

    return () => {
      mounted = false;
    };
  }, [role]);

  const handleLogout = async () => {
    await authService.logout();
    navigate("/login", { replace: true });
  };

  const toggleTheme = () => {
    const nextTheme = themeHint === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem("theme", nextTheme);
    setThemeHint(nextTheme);
  };

  return (
    <header className="dashboard-topbar sticky top-0 z-50 shrink-0 border-b border-header-border bg-header/95 pt-[env(safe-area-inset-top)] text-header-text backdrop-blur-md">
      <div className="mx-auto flex h-[3.75rem] w-full max-w-[1320px] items-center gap-1.5 px-2 sm:gap-2 sm:px-5 md:h-16 lg:px-8">
        <button
          type="button"
          className={cn(headerIconButtonClass, "md:hidden")}
          onClick={onOpenMobileNav}
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div className="min-w-0 flex-1">
          <p className="hidden truncate text-[10px] font-bold uppercase tracking-[0.12em] text-header-muted sm:block sm:text-xs">Learnly AI</p>
          <p className="truncate text-xs font-semibold text-header-text sm:text-lg">{schoolName || roleLabels[role] || "Workspace"}</p>
        </div>

        {canSearchWorkspace && (
          <div className="hidden w-full max-w-md md:block">
            <WorkspaceSearch role={role} />
          </div>
        )}

        <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
          <Dropdown
            align="right"
            className="w-80 max-w-[calc(100vw-1rem)]"
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
              {notifications.length > 0 ? (
                notifications.map((item) => (
                  <div key={item.id} className="rounded-xl border border-border bg-surface px-3 py-2">
                    <p className="line-clamp-1 text-sm font-semibold text-text">{item.title}</p>
                    <p className="mt-1 line-clamp-2 text-xs text-text-muted">{item.message}</p>
                    <p className="mt-1 text-[11px] text-text-faint">{notificationTimestamp(item.created_at)}</p>
                  </div>
                ))
              ) : (
                <p className="rounded-xl border border-dashed border-border px-3 py-4 text-sm text-text-muted">No notifications yet.</p>
              )}
            </div>
          </Dropdown>

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
            trigger={
              <button type="button" className="flex h-10 items-center gap-2 rounded-full border border-header-border/60 bg-header-surface/90 px-2 py-1 text-header-muted shadow-[0_10px_24px_rgba(15,23,42,0.12)] transition hover:bg-header-surface-hover hover:text-header-text">
                <Avatar src={avatarSrc} name={userName} size="sm" />
                <span className="hidden max-w-[10rem] flex-col items-start leading-tight sm:flex">
                  <span className="max-w-full truncate text-sm font-semibold text-header-text">{userName}</span>
                  {showPlanBadge ? <span className="mt-0.5 text-[10px] font-semibold uppercase tracking-wide text-header-muted">{formatPlanName(planCode)}</span> : null}
                </span>
                <ChevronDown className="h-4 w-4 text-header-muted" />
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
                {showPlanBadge ? <p className="mt-3 text-xs text-text-muted">{formatPlanName(planCode)} - {statusMeta?.label || "Plan status"}</p> : null}
              </div>
              <Link to="/profile" className="block rounded-xl px-3 py-2 text-sm font-medium text-text-soft hover:bg-surface-muted">Profile settings</Link>
              <Link to="/legal" className="block rounded-xl px-3 py-2 text-sm font-medium text-text-soft hover:bg-surface-muted">Legal</Link>
              <button type="button" onClick={handleLogout} className="mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-semibold text-error hover:bg-error-soft">
                <LogOut className="h-4 w-4" /> Logout
              </button>
            </div>
          </Dropdown>
        </div>
      </div>
      {canSearchWorkspace ? (
        <div className="border-t border-header-border/70 px-3 py-2 md:hidden">
          <WorkspaceSearch role={role} />
        </div>
      ) : null}
    </header>
  );
}
