import { api } from "./api";
import {
  buildChangedPatch,
  hasPatchChanges,
  mergePatchResult,
  rememberById,
  rememberRecord,
} from "./patchPayload";

const reportCardsById = new Map();

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

const rememberGenerated = (response) => {
  if (Array.isArray(response?.generated)) {
    response.generated.forEach((item) => rememberRecord(reportCardsById, item));
    return response;
  }
  return rememberRecord(reportCardsById, response);
};

export const reportCardService = {
  listAdminReportCards: async (params, requestOptions) => {
    const response = await api.get(
      `/tenant-admin/academic/report-cards${queryString(params)}`,
      requestOptions,
    );
    return rememberById(reportCardsById, response);
  },
  getAdminReportCard: async (reportCardId, requestOptions) => {
    const response = await api.get(
      `/tenant-admin/academic/report-cards/${reportCardId}`,
      requestOptions,
    );
    return rememberRecord(reportCardsById, response);
  },
  getClassOverview: (params) =>
    api.get(`/tenant-admin/academic/report-cards/overview${queryString(params)}`),
  generateReportCard: async (payload) => {
    const response = await api.post(
      "/tenant-admin/academic/report-cards/generate",
      payload,
    );
    return rememberGenerated(response);
  },
  regenerateReportCard: async (reportCardId) => {
    const response = await api.post(
      `/tenant-admin/academic/report-cards/${reportCardId}/regenerate`,
    );
    return rememberRecord(reportCardsById, response);
  },
  updateReportCardComments: async (reportCardId, payload) => {
    const key = String(reportCardId);
    const current = reportCardsById.get(key);
    const changes = buildChangedPatch(current, payload);
    if (!hasPatchChanges(changes)) return current;

    const response = await api.patch(
      `/tenant-admin/academic/report-cards/${reportCardId}/comments`,
      changes,
    );
    reportCardsById.set(key, mergePatchResult(current, changes, response));
    return response;
  },
  publishReportCard: async (reportCardId) => {
    const response = await api.post(
      `/tenant-admin/academic/report-cards/${reportCardId}/publish`,
    );
    return rememberRecord(reportCardsById, response);
  },

  listMyReportCards: (params = {}, requestOptions) =>
    api.get(`/students/me/academic/report-cards${queryString(params)}`, requestOptions),
  getMyReportCard: (reportCardId, requestOptions) =>
    api.get(`/students/me/academic/report-cards/${reportCardId}`, requestOptions),
  listChildReportCards: (studentId, params = {}, requestOptions) =>
    api.get(
      `/parents/me/children/${studentId}/academic/report-cards${queryString(params)}`,
      requestOptions,
    ),
  getChildReportCard: (studentId, reportCardId, requestOptions) =>
    api.get(`/parents/me/children/${studentId}/academic/report-cards/${reportCardId}`, requestOptions),
};

export default reportCardService;
