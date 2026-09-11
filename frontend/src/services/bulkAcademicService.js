import { api } from "./api";

export const bulkAcademicService = {
  transitionClassResults: (payload) =>
    api.post("/tenant-admin/academics/results/bulk/transition", payload),

  reopenClassResults: (payload) =>
    api.post("/tenant-admin/academics/results/bulk/reopen", payload),

  publishClassReportCards: (payload) =>
    api.post("/tenant-admin/academic/report-cards/bulk/publish", payload),

  archiveClassReportCards: (payload) =>
    api.post("/tenant-admin/academic/report-cards/bulk/archive", payload),

  reopenClassReportCards: (payload) =>
    api.post("/tenant-admin/academic/report-cards/bulk/reopen", payload),
};

export default bulkAcademicService;
