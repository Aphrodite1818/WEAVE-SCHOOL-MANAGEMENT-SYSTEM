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

const announcementSnapshots = new Map();

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

const announcementBasePath = (mode) =>
  mode === "superadmin"
    ? "/superadmin/announcements"
    : "/tenant-admin/announcements";

export const communicationAnnouncementService = {
  list: async (mode, params) => {
    const response = await api.get(withQuery(announcementBasePath(mode), params));
    return rememberById(announcementSnapshots, response);
  },
  create: async (mode, payload) => {
    const response = await api.post(announcementBasePath(mode), payload);
    return rememberRecord(announcementSnapshots, response);
  },
  update: async (mode, id, payload) => {
    const key = String(id);
    const current = announcementSnapshots.get(key);
    const changes = buildChangedPatch(current, payload);
    if (!hasPatchChanges(changes)) return current;

    const response = await api.patch(
      `${announcementBasePath(mode)}/${id}`,
      changes,
    );
    announcementSnapshots.set(
      key,
      mergePatchResult(current, changes, response),
    );
    return response;
  },
  preview: (mode, payload) =>
    api.post(`${announcementBasePath(mode)}/preview`, payload),
  publish: async (mode, id, payload = {}) => {
    const response = await api.post(
      `${announcementBasePath(mode)}/${id}/publish`,
      payload,
    );
    return rememberRecord(announcementSnapshots, response);
  },
  archive: async (mode, id) => {
    const response = await api.post(
      `${announcementBasePath(mode)}/${id}/archive`,
      {},
    );
    return rememberRecord(announcementSnapshots, response);
  },
  cancel: async (mode, id) => {
    const response = await api.post(
      `${announcementBasePath(mode)}/${id}/cancel`,
      {},
    );
    return rememberRecord(announcementSnapshots, response);
  },
};
