import { api } from "./api";

const clampLimit = (limit) => Math.min(Math.max(Number(limit) || 100, 1), 100);

const buildStudentQuery = ({ skip = 0, limit = 100, search, classId, status } = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(skip));
  params.set("limit", String(clampLimit(limit)));
  if (search) params.set("search", search);
  if (classId) params.set("class_id", classId);
  if (status) params.set("status", status);
  return params.toString();
};

export const studentService = {
  getStudents: (options = {}) =>
    api.get(`/students?${buildStudentQuery(options)}`),

  getAdminStudents: (options = {}) =>
    api.get(`/tenant-admin/students?${buildStudentQuery(options)}`),

  createStudent: (payload) =>
    api.post("/tenant-admin/students", payload),

  resetStudentAccessCode: (studentId) =>
    api.post(`/tenant-admin/students/${studentId}/reset-access-code`),

  getMyStudent: (requestOptions) =>
    api.get("/students/me", requestOptions),

  updateMyStudentProfile: (payload) =>
    api.patch("/students/me/profile", payload),

  changeMyPassword: (payload) =>
    api.post("/students/me/change-password", payload),

  getMyParentLinkRequests: (requestOptions) =>
    api.get("/students/me/parent-link-requests", requestOptions),

  respondToParentLinkRequest: (requestId, payload) =>
    api.post(`/students/me/parent-link-requests/${requestId}/respond`, payload),

  getMyParentLinks: (requestOptions) =>
    api.get("/students/me/parent-links", requestOptions),

  getStudent: (studentId) =>
    api.get(`/students/${studentId}`),

  getAdminStudent: (studentId) =>
    api.get(`/tenant-admin/students/${studentId}`),

  updateStudent: (studentId, payload) =>
    api.patch(`/students/${studentId}`, payload),

  updateAdminStudent: (studentId, payload) =>
    api.patch(`/tenant-admin/students/${studentId}`, payload),

  deleteStudent: (studentId) =>
    api.delete(`/tenant-admin/students/${studentId}`),

  completeStudentProfile: (studentId, payload) =>
    api.patch(`/tenant-admin/students/${studentId}/complete-profile`, payload),

  createParentLink: (payload) =>
    api.post("/tenant-admin/student-parent-links", payload),

  updateParentLink: (linkId, payload) =>
    api.patch(`/tenant-admin/student-parent-links/${linkId}`, payload),

  deleteParentLink: (linkId) =>
    api.delete(`/tenant-admin/student-parent-links/${linkId}`),
};
