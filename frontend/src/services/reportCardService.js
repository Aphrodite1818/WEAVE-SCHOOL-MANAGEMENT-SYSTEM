import { api } from "./api";

const queryString = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (key === "signal") return;
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const value = query.toString();
  return value ? `?${value}` : "";
};

export const reportCardService = {
  listAdminReportCards: (params, requestOptions) =>
    api.get(`/tenant-admin/academic/report-cards${queryString(params)}`, requestOptions),
  getClassOverview: (params) =>
    api.get(`/tenant-admin/academic/report-cards/overview${queryString(params)}`),
  generateReportCard: (payload) =>
    api.post("/tenant-admin/academic/report-cards/generate", payload),
  regenerateReportCard: (reportCardId) =>
    api.post(`/tenant-admin/academic/report-cards/${reportCardId}/regenerate`),
  updateReportCardComments: (reportCardId, payload) =>
    api.patch(`/tenant-admin/academic/report-cards/${reportCardId}/comments`, payload),
  publishReportCard: (reportCardId) =>
    api.post(`/tenant-admin/academic/report-cards/${reportCardId}/publish`),

  listMyReportCards: (requestOptions) => api.get("/students/me/academic/report-cards", requestOptions),
  getMyReportCard: (reportCardId, requestOptions) =>
    api.get(`/students/me/academic/report-cards/${reportCardId}`, requestOptions),
  listChildReportCards: (studentId, requestOptions) =>
    api.get(`/parents/me/children/${studentId}/academic/report-cards`, requestOptions),
  getChildReportCard: (studentId, reportCardId, requestOptions) =>
    api.get(`/parents/me/children/${studentId}/academic/report-cards/${reportCardId}`, requestOptions),
};

export default reportCardService;
