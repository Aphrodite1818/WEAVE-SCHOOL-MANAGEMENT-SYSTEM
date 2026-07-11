import { HelpCircle, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";

import defaultLogoImage from "../../assets/images/favicon.png";
import { authSession } from "../../services/api";
import { cn } from "../../utils/cn";
import { navGroups, roleLabels } from "./navConfig";

function isRouteActive(pathname, itemPath) {
  return pathname === itemPath || (itemPath !== "/" && pathname.startsWith(`${itemPath}/`));
}

function resolveWorkspaceLogo(user) {
  return (
    user?.tenant_logo_url ||
    user?.tenant?.logo_url ||
    user?.logo_url ||
    defaultLogoImage
  );
}

export default function SidebarContent({
  role,
  collapsed,
  onToggleCollapsed,
  onNavigate,
  mobile = false,
  schoolName,
}) {
  const location = useLocation();
  const user = authSession.getUser() || {};
  const workspaceLogo = resolveWorkspaceLogo(user);
  const workspaceLogoAlt = user?.tenant_logo_url || user?.tenant?.logo_url
    ? `${schoolName || "School"} logo`
    : "Learnly AI";
  const groups = navGroups[role] || navGroups.admin;
  const navRef = useRef(null);
  const scrollStorageKey = `learnly-sidebar-scroll:${role}:${mobile ? "mobile" : "desktop"}`;

  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    const navElement = navRef.current;
    if (!navElement) return undefined;

    const savedScroll = Number(window.sessionStorage.getItem(scrollStorageKey) || 0);
    const frameId = window.requestAnimationFrame(() => {
      navElement.scrollTop = savedScroll;
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [scrollStorageKey, collapsed]);

  const persistSidebarScroll = () => {
    if (typeof window === "undefined") return;

    const navElement = navRef.current;
    if (!navElement) return;

    window.sessionStorage.setItem(scrollStorageKey, String(navElement.scrollTop));
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div
        className={cn(
          "relative flex h-[4.5rem] shrink-0 items-center border-b border-border/60 transition-all duration-300",
          collapsed ? "justify-center px-2" : "gap-2 px-3"
        )}
      >
        <Link
          to="/"
          className={cn("flex min-w-0 items-center gap-2.5", collapsed && "justify-center")}
          onClick={() => {
            persistSidebarScroll();
            onNavigate?.();
          }}
        >
          <img
            src={workspaceLogo}
            alt={workspaceLogoAlt}
            className="h-9 w-9 rounded-xl bg-surface object-contain p-1 shadow-sm"
            onError={(event) => {
              if (event.currentTarget.src !== defaultLogoImage) {
                event.currentTarget.src = defaultLogoImage;
              }
            }}
          />
          {!collapsed && (
            <span className="min-w-0">
              <span className="block truncate text-[15px] font-bold leading-tight text-text">
                {schoolName || "Learnly AI"}
              </span>
              <span className="block truncate text-[11px] font-medium text-text-muted">School Management</span>
            </span>
          )}
        </Link>

        {!mobile && (
          <button
            type="button"
            className={cn(
              "inline-flex h-7 w-7 items-center justify-center rounded-lg bg-surface-muted/60 text-text-muted shadow-sm transition hover:bg-surface-muted hover:text-text",
              collapsed ? "absolute -right-3.5 top-1/2 -translate-y-1/2" : "ml-auto"
            )}
            onClick={onToggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <PanelLeftOpen className="h-3.5 w-3.5" /> : <PanelLeftClose className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>

      {!collapsed && (
        <div className="mx-3 mt-3 rounded-xl border border-border/60 bg-surface-muted/40 px-3 py-2.5">
          <p className="truncate text-[11px] font-semibold uppercase tracking-[0.08em] text-text-faint">Workspace</p>
          <p className="mt-1 truncate text-[13px] font-semibold text-text">{schoolName || "School workspace"}</p>
          <span className="mt-2 inline-flex items-center rounded-md bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary">
            {roleLabels[role] || "Workspace"}
          </span>
        </div>
      )}

      <nav
        ref={navRef}
        onScroll={persistSidebarScroll}
        className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-2.5 py-3 pb-[max(1rem,env(safe-area-inset-bottom))]"
      >
        {groups.map((group) => (
          <div key={group.label}>
            {!collapsed && (
              <p className="mb-1.5 px-2.5 text-[10px] font-bold uppercase tracking-[0.1em] text-text-faint">{group.label}</p>
            )}
            <div className="space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive = isRouteActive(location.pathname, item.to);

                return (
                  <Link
                    key={`${group.label}-${item.label}`}
                    to={item.to}
                    onClick={() => {
                      persistSidebarScroll();
                      onNavigate?.();
                    }}
                    title={collapsed ? item.label : undefined}
                    className={cn(
                      "group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-all duration-150",
                      isActive
                        ? "bg-primary text-white shadow-sm"
                        : "text-text-soft hover:bg-surface-muted hover:text-text",
                      collapsed && "justify-center px-2"
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {collapsed && (
                      <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2 whitespace-nowrap rounded-lg border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-text opacity-0 shadow-premium transition-opacity duration-150 group-hover:opacity-100">
                        {item.label}
                      </span>
                    )}
                    {!collapsed && <span className="truncate">{item.label}</span>}
                    {!collapsed && isActive && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-white/70" />}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {!collapsed && (
        <div className="shrink-0 border-t border-border/60 p-2.5">
          <div className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[12px] text-text-muted">
            <HelpCircle className="h-4 w-4" />
            Help & Support
          </div>
        </div>
      )}
    </div>
  );
}
