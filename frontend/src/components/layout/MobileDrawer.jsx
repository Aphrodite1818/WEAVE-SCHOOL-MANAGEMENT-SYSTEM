import { X } from "lucide-react";

import SidebarContent from "./Sidebar";

export default function MobileDrawer({ open, role, schoolName, onClose }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 md:hidden">
      <div className="absolute inset-0 bg-black/35 backdrop-blur-sm" onClick={onClose} />
      <aside
        data-mobile-drawer="true"
        className="absolute inset-y-0 left-0 flex h-full w-[min(88vw,20rem)] flex-col overflow-hidden border-r border-border bg-surface shadow-2xl"
      >
        <div className="flex h-14 shrink-0 items-center justify-end px-4">
          <button
            type="button"
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-surface-muted/60 text-text-muted transition hover:bg-surface-muted hover:text-text"
            onClick={onClose}
            aria-label="Close navigation"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="min-h-0 flex-1">
          <SidebarContent
            role={role}
            mobile
            collapsed={false}
            onNavigate={onClose}
            schoolName={schoolName}
          />
        </div>
      </aside>
    </div>
  );
}
