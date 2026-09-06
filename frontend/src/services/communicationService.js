import { api } from "./api";
import {
  buildChangedPatch,
  hasPatchChanges,
  mergePatchResult,
  rememberById,
  rememberRecord,
} from "./patchPayload";

export const NOTIFICATIONS_CHANGED_EVENT = "weave:notifications-changed";
export const NOTIFICATION_REALTIME_EVENTS = [
  "notification.created",
  "notification.updated",
  "notification.dismissed",
];
export const MESSAGE_REALTIME_EVENTS = ["message.created", "message.read"];
export const NOTICE_REALTIME_EVENTS = [
  "notice.published",
  ...NOTIFICATION_REALTIME_EVENTS,
];

const noticeSnapshots = new Map();

export function emitNotificationsChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(NOTIFICATIONS_CHANGED_EVENT));
  }
}

const withQuery = (path, params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "")
      query.set(key, value);
  });
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
};

export const notificationService = {
  list: (params) => api.get(withQuery("/notifications", params)),
  unreadCount: () => api.get("/notifications/unread-count"),
  get: (id) => api.get(`/notifications/${id}`),
  markRead: (id) => api.post(`/notifications/${id}/read`, {}),
  acknowledge: (id) => api.post(`/notifications/${id}/acknowledge`, {}),
  dismiss: (id) => api.delete(`/notifications/${id}`),
};

export const inboxService = {
  list: (params) => api.get(withQuery("/inbox", params)),
  unreadCount: () => api.get("/inbox/unread-count"),
  markRead: (id) => api.post(`/inbox/${id}/read`, {}),
};

export const messageService = {
  availableRecipients: () => api.get("/communications/available-recipients"),
  listConversations: (params) =>
    api.get(withQuery("/messages/conversations", params)),
  createConversation: (payload) => api.post("/messages/conversations", payload),
  getConversation: (id) => api.get(`/messages/conversations/${id}`),
  sendMessage: (id, payload) =>
    api.post(`/messages/conversations/${id}/messages`, payload),
  markRead: (id) => api.post(`/messages/conversations/${id}/read`, {}),
};

export const noticeService = {
  listReceived: (params) => api.get(withQuery("/notices", params)),
  markRead: (id) => api.post(`/notices/${id}/read`, {}),
};

const noticeBasePath = (mode) => {
  if (mode === "superadmin") return "/superadmin/notices";
  if (mode === "teacher") return "/teacher/notices";
  return "/tenant-admin/notices";
};

export const communicationNoticeService = {
  list: async (mode, params) => {
    const response = await api.get(withQuery(noticeBasePath(mode), params));
    return rememberById(noticeSnapshots, response);
  },
  create: async (mode, payload) => {
    const response = await api.post(noticeBasePath(mode), payload);
    return rememberRecord(noticeSnapshots, response);
  },
  update: async (mode, id, payload) => {
    const key = String(id);
    const current = noticeSnapshots.get(key);
    const changes = buildChangedPatch(current, payload);
    if (!hasPatchChanges(changes)) return current;
    const response = await api.patch(`${noticeBasePath(mode)}/${id}`, changes);
    noticeSnapshots.set(key, mergePatchResult(current, changes, response));
    return response;
  },
  preview: (mode, payload) =>
    api.post(`${noticeBasePath(mode)}/preview`, payload),
  publish: async (mode, id, payload = {}) => {
    const response = await api.post(
      `${noticeBasePath(mode)}/${id}/publish`,
      payload,
    );
    return rememberRecord(noticeSnapshots, response);
  },
  archive: async (mode, id) => {
    const response = await api.post(`${noticeBasePath(mode)}/${id}/archive`, {});
    return rememberRecord(noticeSnapshots, response);
  },
  cancel: async (mode, id) => {
    const response = await api.post(`${noticeBasePath(mode)}/${id}/cancel`, {});
    return rememberRecord(noticeSnapshots, response);
  },
};
