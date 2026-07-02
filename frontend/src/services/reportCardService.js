import { API_BASE_URL, api, authSession } from "./api";

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

const openPrintWindow = async (endpoint) => {
  const printWindow = window.open("", "_blank");
  if (!printWindow) {
    throw new Error("Allow pop-ups to view or print this report card.");
  }

  printWindow.document.write("<p>Loading report card...</p>");

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: {
        Authorization: `Bearer ${authSession.getToken()}`,
      },
    });

    if (!response.ok) {
      throw new Error("Could not load this report card.");
    }

    const html = await response.text();
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
  } catch (error) {
    printWindow.document.open();
    printWindow.document.write(`<p>${error.message}</p>`);
    printWindow.document.close();
    throw error;
  }
};

export const reportCardService = {
  listAdminReportCards: (params) =>
    api.get(`/tenant-admin/academic/report-cards${queryString(params)}`),
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

  listMyReportCards: () => api.get("/students/me/academic/report-cards"),
  listChildReportCards: (studentId) =>
    api.get(`/parents/me/children/${studentId}/academic/report-cards`),

  printAdminReportCard: (reportCardId) =>
    openPrintWindow(`/tenant-admin/academic/report-cards/${reportCardId}/print`),
  printStudentReportCard: (reportCardId) =>
    openPrintWindow(`/students/me/academic/report-cards/${reportCardId}/print`),
  printParentReportCard: (studentId, reportCardId) =>
    openPrintWindow(`/parents/me/children/${studentId}/academic/report-cards/${reportCardId}/print`),
};

export default reportCardService;
