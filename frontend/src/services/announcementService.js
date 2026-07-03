import { api, authSession } from "./api";

const clampLimit = (limit) => Math.min(Math.max(Number(limit) || 50, 1), 100);

const withQuery = (endpoint, params = {}) => {
  const query = new URLSearchParams();

  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, key === "limit" ? clampLimit(value) : value);
    }
  });

  const queryString = query.toString();
  return queryString ? `${endpoint}?${queryString}` : endpoint;
};

const getCurrentRole = () =>
  String(authSession.getUser()?.role || authSession.getRole() || "").toLowerCase();

const isDirectTeacherMessagePayload = (payload = {}) =>
  Array.isArray(payload.targets) &&
  payload.targets.length > 0 &&
  payload.targets.every((target) => target?.target_type === "specific_teacher" && target?.teacher_id);

const createdAtMs = (item) => {
  const date = new Date(item?.created_at || item?.publish_at || 0);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
};

const mergeFeedResponses = (primary = {}, secondary = {}, limit = 50) => {
  const byId = new Map();

  [...(primary.items || []), ...(secondary.items || [])].forEach((item) => {
    if (item?.id) byId.set(item.id, item);
  });

  const items = Array.from(byId.values())
    .sort((left, right) => createdAtMs(right) - createdAtMs(left))
    .slice(0, clampLimit(limit));

  return {
    ...primary,
    items,
    total: Math.max(Number(primary.total || 0), 0) + Math.max(Number(secondary.total || 0), 0),
    unread_count: items.filter((item) => !item.is_read).length,
  };
};

const createTenantAdminAnnouncement = async (payload) => {
  const created = await api.post("/tenant-admin/announcements", payload);

  if (isDirectTeacherMessagePayload(payload) && created?.id) {
    return api.post(`/tenant-admin/announcements/${created.id}/publish`, {});
  }

  return created;
};

const getTeacherFeed = async (params = {}) => {
  const limit = params?.limit ?? 50;
  const noticeParams = { ...params, delivery_kind: params?.delivery_kind || undefined };

  if (params?.delivery_kind === "message") {
    return api.get(withQuery("/teachers/me/messages", { skip: params.skip, limit }));
  }

  if (params?.delivery_kind === "notice") {
    const [notices, messages] = await Promise.all([
      api.get(withQuery("/announcements/feed", noticeParams)),
      api.get(withQuery("/teachers/me/messages", { skip: params.skip, limit })),
    ]);
    return mergeFeedResponses(notices, messages, limit);
  }

  const [feed, messages] = await Promise.all([
    api.get(withQuery("/announcements/feed", params)),
    api.get(withQuery("/teachers/me/messages", { skip: params.skip, limit })),
  ]);

  return mergeFeedResponses(feed, messages, limit);
};

export const announcementService = {
  listSuperadminAnnouncements: (params) =>
    api.get(withQuery("/superadmin/announcements", params)),
  getSuperadminAnnouncement: (id) =>
    api.get(`/superadmin/announcements/${id}`),
  createSuperadminAnnouncement: (payload) =>
    api.post("/superadmin/announcements", payload),
  updateSuperadminAnnouncement: (id, payload) =>
    api.patch(`/superadmin/announcements/${id}`, payload),
  publishSuperadminAnnouncement: (id, payload = {}) =>
    api.post(`/superadmin/announcements/${id}/publish`, payload),
  archiveSuperadminAnnouncement: (id, payload = {}) =>
    api.post(`/superadmin/announcements/${id}/archive`, payload),
  deleteSuperadminAnnouncement: (id) =>
    api.delete(`/superadmin/announcements/${id}`),

  listTenantAdminAnnouncements: (params) =>
    api.get(withQuery("/tenant-admin/announcements", params)),
  getTenantAdminAnnouncement: (id) =>
    api.get(`/tenant-admin/announcements/${id}`),
  createTenantAdminAnnouncement,
  updateTenantAdminAnnouncement: (id, payload) =>
    api.patch(`/tenant-admin/announcements/${id}`, payload),
  publishTenantAdminAnnouncement: (id, payload = {}) =>
    api.post(`/tenant-admin/announcements/${id}/publish`, payload),
  archiveTenantAdminAnnouncement: (id, payload = {}) =>
    api.post(`/tenant-admin/announcements/${id}/archive`, payload),
  deleteTenantAdminAnnouncement: (id) =>
    api.delete(`/tenant-admin/announcements/${id}`),

  listTeacherAnnouncements: (params) =>
    api.get(withQuery("/teachers/me/announcements", params)),
  getTeacherAnnouncement: (id) =>
    api.get(`/teachers/me/announcements/${id}`),
  createTeacherAnnouncement: (payload) =>
    api.post("/teachers/me/announcements", payload),
  updateTeacherAnnouncement: (id, payload) =>
    api.patch(`/teachers/me/announcements/${id}`, payload),
  publishTeacherAnnouncement: (id, payload = {}) =>
    api.post(`/teachers/me/announcements/${id}/publish`, payload),
  archiveTeacherAnnouncement: (id, payload = {}) =>
    api.post(`/teachers/me/announcements/${id}/archive`, payload),
  deleteTeacherAnnouncement: (id) =>
    api.delete(`/teachers/me/announcements/${id}`),

  listTeacherMessages: (params) =>
    api.get(withQuery("/teachers/me/messages", params)),

  getFeed: (params) =>
    getCurrentRole() === "teacher"
      ? getTeacherFeed(params)
      : api.get(withQuery("/announcements/feed", params)),
  markRead: (id) => api.post(`/announcements/${id}/read`, {}),
  acknowledge: (id) => api.post(`/announcements/${id}/acknowledge`, {}),
};
