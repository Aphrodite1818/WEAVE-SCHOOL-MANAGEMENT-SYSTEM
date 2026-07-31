import { API_BASE_URL, api, authSession } from "./api";
import { clearDashboardMetricsCache } from "./dashboard.service";

const STUDENT_RESOURCE_TYPE = "students";

const getAuthHeaders = () => {
  const token = authSession.getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const buildApiError = async (response, fallback) => {
  const data = await response.json().catch(() => ({ detail: fallback }));
  const error = new Error(data?.detail || data?.message || fallback);
  error.response = {
    status: response.status,
    data,
    headers: Object.fromEntries(response.headers.entries()),
  };
  return error;
};

const fetchJsonWithBody = async (endpoint, { method = "GET", body, signal, fallback } = {}) => {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method,
    headers: getAuthHeaders(),
    body,
    signal,
  });

  if (!response.ok) {
    throw await buildApiError(response, fallback || "Bulk import request failed.");
  }

  return response.json();
};

const downloadBlob = async (endpoint, filename, signal) => {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "GET",
    headers: getAuthHeaders(),
    signal,
  });

  if (!response.ok) {
    throw await buildApiError(response, "Download failed.");
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
};

const invalidateImportRelatedCaches = () => {
  clearDashboardMetricsCache();
  window.dispatchEvent(new Event("weave:dashboard-cache-clear"));
};

export const bulkImportService = {
  listTemplates: (requestOptions) => api.get("/tenant-admin/imports/templates", requestOptions),

  downloadTemplate: (requestOptions = {}) =>
    downloadBlob(
      `/tenant-admin/imports/templates/${STUDENT_RESOURCE_TYPE}/download`,
      "students_import_template.xlsx",
      requestOptions.signal,
    ),

  dryRun: (file, requestOptions = {}) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("notify_on_completion", "true");

    return fetchJsonWithBody(`/tenant-admin/imports/${STUDENT_RESOURCE_TYPE}/dry-run`, {
      method: "POST",
      body: formData,
      signal: requestOptions.signal,
      fallback: "Could not validate the import file.",
    });
  },

  confirm: async (jobId, requestOptions = {}) => {
    const result = await api.post(`/tenant-admin/imports/${jobId}/confirm`, undefined, requestOptions);
    invalidateImportRelatedCaches();
    return result;
  },

  retry: async (jobId, requestOptions = {}) => {
    const result = await api.post(`/tenant-admin/imports/${jobId}/retry`, undefined, requestOptions);
    invalidateImportRelatedCaches();
    return result;
  },

  getJob: (jobId, requestOptions) => api.get(`/tenant-admin/imports/${jobId}`, requestOptions),

  listJobs: ({ skip = 0, limit = 20, status, signal } = {}) => {
    const params = new URLSearchParams({
      skip: String(skip),
      limit: String(limit),
    });
    if (status) params.set("status", status);
    return api.get(`/tenant-admin/imports?${params.toString()}`, { signal });
  },

  deleteJob: async (jobId, requestOptions = {}) => {
    const result = await api.delete(`/tenant-admin/imports/${jobId}`, requestOptions);
    invalidateImportRelatedCaches();
    return result;
  },

  getErrors: (jobId, requestOptions) =>
    api.get(`/tenant-admin/imports/${jobId}/errors?limit=100`, requestOptions),

  getSlipSummary: (jobId, requestOptions) =>
    api.get(`/tenant-admin/imports/${jobId}/slips/summary`, requestOptions),

  listSlips: (
    jobId,
    {
      search = "",
      classKey = "",
      page = 1,
      pageSize = 50,
      signal,
    } = {},
  ) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (search) params.set("search", search);
    if (classKey) params.set("class_key", classKey);
    return api.get(`/tenant-admin/imports/${jobId}/slips?${params.toString()}`, { signal });
  },

  getSlip: (jobId, rowNumber, requestOptions) =>
    api.get(`/tenant-admin/imports/${jobId}/slips/${rowNumber}`, requestOptions),

  getSlipPrintData: (jobId, payload, requestOptions) =>
    api.post(`/tenant-admin/imports/${jobId}/slips/print`, payload, requestOptions),

  downloadResult: (jobId, { format = "spreadsheet", signal } = {}) => {
    const safeFormat = format === "slip" ? "slip" : "spreadsheet";
    const extension = safeFormat === "slip" ? "html" : "xlsx";
    const label = safeFormat === "slip" ? "student_access_slips" : "result";

    return downloadBlob(
      `/tenant-admin/imports/${jobId}/result?format=${safeFormat}`,
      `students_${jobId}_${label}.${extension}`,
      signal,
    );
  },

  downloadErrors: (jobId, { signal } = {}) =>
    downloadBlob(
      `/tenant-admin/imports/${jobId}/errors/download`,
      `students_${jobId}_errors.csv`,
      signal,
    ),
};
