import { useCallback, useEffect, useState } from "react";
import { Check, Megaphone } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import { authSession, getErrorMessage } from "../../services/api";
import {
  NOTICE_REALTIME_EVENTS,
  emitNotificationsChanged,
  noticeService,
} from "../../services/communicationService";
import { realtimeClient } from "../../services/realtimeClient";

const PAGE_SIZE = 20;

function formatTimestamp(value) {
  if (!value) return "";
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function NoticesPage() {
  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await noticeService.listReceived({
        skip: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setItems(response?.items || []);
      setTotal(Number(response?.total || response?.items?.length || 0));
      setUnreadCount(Number(response?.unread_count || 0));
    } catch (err) {
      setError(getErrorMessage(err, "Could not load notices."));
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const unsubscribers = NOTICE_REALTIME_EVENTS.map((eventType) =>
      realtimeClient.subscribe(eventType, load),
    );
    unsubscribers.push(
      realtimeClient.subscribeConnection((state) => {
        if (state.status === "reconnected") load();
      }),
    );
    return () => unsubscribers.forEach((unsubscribe) => unsubscribe());
  }, [load]);

  const markRead = async (item) => {
    try {
      await noticeService.markRead(item.id);
      emitNotificationsChanged();
      await load();
    } catch (err) {
      setError(getErrorMessage(err, "Could not mark this notice as read."));
    }
  };

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const role = String(authSession?.getUser?.()?.role || "admin").toLowerCase();

  return (
    <DashboardLayout
      role={role}
      title="Notices"
      description={`${unreadCount} unread notice${unreadCount === 1 ? "" : "s"}`}
      actions={
        <Button variant="outline" className="manual-refresh-action" onClick={load}>
          Refresh
        </Button>
      }
    >
      <section className="flex w-full flex-col gap-4 sm:gap-5">
        {loading ? <LoadingState label="Loading notices" /> : null}
        {!loading && error ? (
          <div className="rounded-xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">{error}</div>
        ) : null}
        {!loading && !error && !items.length ? (
          <EmptyState
            icon={Megaphone}
            title="No notices yet"
            description="School notices addressed to you will appear here."
          />
        ) : null}
        {!loading && !error && items.length ? (
          <div className="space-y-3">
            {items.map((item) => {
              const unread = item.delivery_status === "unread";
              return (
                <article key={item.id} className="rounded-2xl border border-border bg-surface p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="font-bold text-text">{item.title}</h2>
                        <span className="rounded-full bg-surface-muted px-2 py-0.5 text-xs font-bold text-text-muted">{item.category}</span>
                        {item.priority !== "normal" ? (
                          <span className="rounded-full bg-primary-soft px-2 py-0.5 text-xs font-bold text-primary">{item.priority}</span>
                        ) : null}
                        {unread ? (
                          <span className="rounded-full bg-primary-soft px-2 py-0.5 text-xs font-bold text-primary">Unread</span>
                        ) : null}
                      </div>
                      <p className="mt-2 whitespace-pre-wrap text-sm text-text-muted">{item.body}</p>
                      <time className="mt-3 block text-xs text-text-faint">{formatTimestamp(item.delivered_at)}</time>
                    </div>
                    {unread ? (
                      <Button size="sm" variant="outline" onClick={() => markRead(item)}>
                        <Check className="h-4 w-4" /> Mark read
                      </Button>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-text-muted">Page {page} of {pageCount}</span>
          <div className="flex gap-2">
            <Button size="small" variant="outline" disabled={page <= 1 || loading} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</Button>
            <Button size="small" variant="outline" disabled={page >= pageCount || loading} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>Next</Button>
          </div>
        </div>
      </section>
    </DashboardLayout>
  );
}
