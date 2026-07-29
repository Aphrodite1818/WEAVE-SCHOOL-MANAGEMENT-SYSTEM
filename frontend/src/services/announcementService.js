import { api } from "./api";

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

const createTenantAdminAnnouncement = (payload) =>
  api.post("/tenant-admin/announcements", payload);

const markRead = (id) => api.post(`/announcements/${id}/read`, {});

const acknowledge = (id) => api.post(`/announcements/${id}/acknowledge`, {});

const deleteReadNotification = (id) => api.delete(`/announcements/${id}/read`);

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

  getFeed: (params) =>
    api.get(withQuery("/announcements/feed", params)),
  markRead,
  acknowledge,
  deleteReadNotification,
};
