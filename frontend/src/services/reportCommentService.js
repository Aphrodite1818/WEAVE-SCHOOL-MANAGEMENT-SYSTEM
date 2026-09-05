import { api } from "./api";

const queryString = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const value = query.toString();
  return value ? `?${value}` : "";
};

export const reportCommentService = {
  listTeacherTemplates: (params) =>
    api.get(`/teachers/me/comment-templates${queryString(params)}`),
  createTeacherTemplate: (payload) =>
    api.post("/teachers/me/comment-templates", payload),
  updateTeacherTemplate: (templateId, payload) =>
    api.patch(`/teachers/me/comment-templates/${templateId}`, payload),
  deleteTeacherTemplate: (templateId) =>
    api.delete(`/teachers/me/comment-templates/${templateId}`),

  listAdminTemplates: (params) =>
    api.get(`/tenant-admin/academic/comment-templates${queryString(params)}`),
  createAdminTemplate: (payload) =>
    api.post("/tenant-admin/academic/comment-templates", payload),
  updateAdminTemplate: (templateId, payload) =>
    api.patch(`/tenant-admin/academic/comment-templates/${templateId}`, payload),
  deleteAdminTemplate: (templateId) =>
    api.delete(`/tenant-admin/academic/comment-templates/${templateId}`),

  listTeacherStudentComments: (params) =>
    api.get(`/teachers/me/student-comments${queryString(params)}`),
  saveTeacherCommentDraft: (studentId, payload) =>
    api.put(`/teachers/me/student-comments/${studentId}/draft`, payload),
  submitTeacherComment: (studentId, payload) =>
    api.post(`/teachers/me/student-comments/${studentId}/submit`, payload),

  overrideTeacherComment: (payload) =>
    api.post(
      "/tenant-admin/academic/report-cards/teacher-comment-overrides",
      payload,
    ),
};

export default reportCommentService;
