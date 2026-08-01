import { useCallback, useEffect, useState } from "react";
import { Bell, Check, Inbox, Mail, Megaphone, Trash2 } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import { authSession, getErrorMessage } from "../../services/api";
import { emitNotificationsChanged, notificationService } from "../../services/communicationService";

const filters = [
  { label: "All", value: "" },
  { label: "Unread", value: "unread" },
  { label: "Messages", value: "message" },
  { label: "Announcements", value: "announcement" },
  { label: "System", value: "system_event" },
];

const sourceIcons = {
  message: Mail,
  announcement: Megaphone,
  system_event: Bell,
};
const NOTIFICATION_PAGE_SIZE = 20;

function formatTimestamp(value) {
  if (!value) return "";
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function CommunicationInboxPage() {
  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const skip = (page - 1) * NOTIFICATION_PAGE_SIZE;
      const params = filter === "unread" ? { status: "unread" } : filter ? { source_type: filter } : {};
      const response = await notificationService.list({ ...params, skip, limit: NOTIFICATION_PAGE_SIZE });
      setItems(response?.items || []);
      setTotal(Number(response?.total || response?.items?.length || 0));
      setUnreadCount(Number(response?.unread_count || 0));
    } catch (err) {
      setError(getErrorMessage(err, "Could not load notifications."));
    } finally {
      setLoading(false);
    }
  }, [filter, page]);

  useEffect(() => {
    load();
  }, [load]);

  const mutate = async (action) => {
    await action();
    emitNotificationsChanged();
    await load();
  };
  const pageCount = Math.max(1, Math.ceil(total / NOTIFICATION_PAGE_SIZE));

  const selectFilter = (nextFilter) => {
    setFilter(nextFilter);
    setPage(1);
  };

  return (
    <DashboardLayout
      role={String(authSession?.getUser?.()?.role || "admin").toLowerCase()}
      title="Inbox"
      description={`${unreadCount} unread notification${unreadCount === 1 ? "" : "s"}`}
      actions={<Button variant="outline" className="manual-refresh-action" onClick={load}>Refresh</Button>}
    >
    <section className="flex w-full flex-col gap-4 sm:gap-5">

      <div className="flex flex-wrap gap-2">
        {filters.map((item) => (
          <button
            key={item.value || "all"}
            type="button"
            onClick={() => selectFilter(item.value)}
            className={`rounded-lg border px-3 py-2 text-sm font-semibold ${filter === item.value ? "is-selected-highlight" : "border-border bg-surface text-text-soft"}`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {loading ? <LoadingState label="Loading notifications" /> : null}
      {!loading && error ? <div className="rounded-xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">{error}</div> : null}
      {!loading && !error && !items.length ? <EmptyState icon={Inbox} title="No notifications here yet" /> : null}
      {!loading && !error && items.length ? (
        <div className="mobile-scroll-list divide-y divide-border rounded-2xl border border-border bg-surface">
          {items.map((item) => {
            const Icon = sourceIcons[item.source_type] || Bell;
            const isUnread = item.status === "unread";
            return (
              <article key={item.id} className="flex gap-3 p-4">
                <span className={`mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${isUnread ? "bg-primary-soft text-primary" : "bg-surface-muted text-text-muted"}`}>
                  <Icon className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <h2 className="text-sm font-bold text-text">{item.title}</h2>
                      <p className="mt-1 max-w-3xl text-sm text-text-muted">{item.preview}</p>
                    </div>
                    <time className="text-xs text-text-faint">{formatTimestamp(item.delivered_at)}</time>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {isUnread ? (
                      <Button size="sm" variant="outline" onClick={() => mutate(() => notificationService.markRead(item.id))}>
                        <Check className="h-4 w-4" /> Mark read
                      </Button>
                    ) : null}
                    <Button size="sm" variant="outline" onClick={() => mutate(() => notificationService.acknowledge(item.id))}>
                      <Check className="h-4 w-4" /> Acknowledge
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => mutate(() => notificationService.dismiss(item.id))}>
                      <Trash2 className="h-4 w-4" /> Dismiss
                    </Button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}
      <div className="mobile-list-pagination flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-text-muted">Page {page} of {pageCount}</span>
        <div className="grid grid-cols-2 gap-2 sm:flex">
          <Button type="button" size="small" variant="outline" disabled={loading || page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</Button>
          <Button type="button" size="small" variant="outline" disabled={loading || page >= pageCount} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}>Next</Button>
        </div>
      </div>
    </section>
    </DashboardLayout>
  );
}
