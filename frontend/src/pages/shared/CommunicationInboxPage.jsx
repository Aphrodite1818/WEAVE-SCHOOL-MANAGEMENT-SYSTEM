import { Check, Inbox, MailOpen, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import EmptyState from "../../components/shared/EmptyState";
import LoadingState from "../../components/shared/LoadingState";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import { authSession, getErrorMessage } from "../../services/api";
import {
  NOTIFICATION_REALTIME_EVENTS,
  emitNotificationsChanged,
  inboxService,
} from "../../services/communicationService";
import { realtimeClient } from "../../services/realtimeClient";

const INBOX_PAGE_SIZE = 20;

function formatTimestamp(value) {
  if (!value) return "";
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function CommunicationInboxPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await inboxService.list({
        skip: (page - 1) * INBOX_PAGE_SIZE,
        limit: INBOX_PAGE_SIZE,
      });
      setItems(response?.items || []);
      setTotal(Number(response?.total || response?.items?.length || 0));
      setUnreadCount(Number(response?.unread_count || 0));
    } catch (err) {
      setError(getErrorMessage(err, "Could not load your inbox."));
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const reconcileMessageNotification = (event) => {
      if (event?.data?.source_type === "message") load();
    };
    const unsubscribers = NOTIFICATION_REALTIME_EVENTS.map((eventType) =>
      realtimeClient.subscribe(eventType, reconcileMessageNotification),
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
      await inboxService.markRead(item.id);
      emitNotificationsChanged();
      await load();
    } catch (err) {
      setError(getErrorMessage(err, "Could not mark this message as read."));
    }
  };

  const openMessage = async (item) => {
    try {
      if (item.status === "unread") await inboxService.markRead(item.id);
      emitNotificationsChanged();
      if (item.action_path) navigate(item.action_path);
    } catch (err) {
      setError(getErrorMessage(err, "Could not open this message."));
    }
  };

  const deleteNotification = async (item) => {
    try {
      await inboxService.dismiss(item.id);
      await load();
    } catch (err) {
      setError(getErrorMessage(err, "Could not delete this notification."));
    }
  };

  const pageCount = Math.max(1, Math.ceil(total / INBOX_PAGE_SIZE));

  return (
    <DashboardLayout
      role={String(authSession?.getUser?.()?.role || "admin").toLowerCase()}
      title="Inbox"
      description={`${unreadCount} unread message${unreadCount === 1 ? "" : "s"}`}
      actions={
        <Button
          variant="outline"
          className="manual-refresh-action"
          onClick={load}
        >
          Refresh
        </Button>
      }
    >
      <section className="flex w-full flex-col gap-4 sm:gap-5">
        {loading ? <LoadingState label="Loading inbox" /> : null}
        {!loading && error ? (
          <div className="rounded-xl border border-error/30 bg-error-soft px-4 py-3 text-sm font-semibold text-error">
            {error}
          </div>
        ) : null}
        {!loading && !error && !items.length ? (
          <EmptyState
            icon={Inbox}
            title="Your inbox is clear"
            description="New direct messages sent to you will appear here."
          />
        ) : null}
        {!loading && !error && items.length ? (
          <div className="divide-y divide-border rounded-2xl border border-border bg-surface">
            {items.map((item) => {
              const isUnread = item.status === "unread";
              return (
                <article key={item.id} className="flex gap-3 p-4">
                  <span
                    className={`mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${isUnread ? "bg-primary-soft text-primary" : "bg-surface-muted text-text-muted"}`}
                  >
                    <MailOpen className="h-5 w-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <h2 className="text-sm font-bold text-text">
                            {item.title}
                          </h2>
                          {isUnread ? (
                            <Badge variant="primary" className="px-2 py-1 text-[11px]">
                              Unread
                            </Badge>
                          ) : null}
                        </div>
                        <p className="mt-1 max-w-3xl text-sm text-text-muted">
                          {item.preview}
                        </p>
                      </div>
                      <time className="text-xs text-text-faint">
                        {formatTimestamp(item.delivered_at)}
                      </time>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {isUnread ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => markRead(item)}
                        >
                          <Check className="h-4 w-4" /> Mark read
                        </Button>
                      ) : null}
                      {item.action_path ? (
                        <Button size="sm" onClick={() => openMessage(item)}>
                          <MailOpen className="h-4 w-4" /> Open notification
                        </Button>
                      ) : null}
                      {item.status !== "unread" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => deleteNotification(item)}
                        >
                          <Trash2 className="h-4 w-4" /> Delete
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}
        <div className="mobile-list-pagination flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-text-muted">
            Page {page} of {pageCount}
          </span>
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <Button
              type="button"
              size="small"
              variant="outline"
              disabled={loading || page <= 1}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
            >
              Previous
            </Button>
            <Button
              type="button"
              size="small"
              variant="outline"
              disabled={loading || page >= pageCount}
              onClick={() =>
                setPage((current) => Math.min(pageCount, current + 1))
              }
            >
              Next
            </Button>
          </div>
        </div>
      </section>
    </DashboardLayout>
  );
}
