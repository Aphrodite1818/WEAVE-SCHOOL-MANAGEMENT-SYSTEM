import { api } from "./api";

const clampLimit = (limit) => Math.min(Math.max(Number(limit) || 100, 1), 100);

const buildParentQuery = ({ skip = 0, limit = 100 } = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(skip));
  params.set("limit", String(clampLimit(limit)));
  return params.toString();
};

export const parentService = {
  getParents: (options = {}) =>
    api.get(`/tenant-admin/parents?${buildParentQuery(options)}`),

  createParent: (payload) =>
    api.post("/tenant-admin/parents", payload),

  getMyParent: (requestOptions) =>
    api.get("/parents/me", requestOptions),

  updateMyParentProfile: (payload) =>
    api.patch("/parents/me/profile", payload),

  getMyStudents: (requestOptions) =>
    api.get("/parents/me/students", requestOptions),

  createStudentLinkRequest: (payload) =>
    api.post("/parents/me/student-link-requests", payload),

  getMyStudentLinkRequests: (requestOptions) =>
    api.get("/parents/me/student-link-requests", requestOptions),

  getParent: (parentId) =>
    api.get(`/tenant-admin/parents/${parentId}`),

  updateParent: (parentId, payload) =>
    api.patch(`/tenant-admin/parents/${parentId}`, payload),

  deleteParent: (parentId) =>
    api.delete(`/tenant-admin/parents/${parentId}`),
};
