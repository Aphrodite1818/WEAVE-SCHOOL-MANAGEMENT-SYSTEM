import { API_BASE_URL, api, authSession } from "./api";
import { clearDashboardMetricsCache } from "./dashboard.service";

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

export const bulkImportService = {
  listTemplates: (requestOptions) => api.get("/tenant-admin/imports/templates", requestOptions),

  downloadTemplate: (resourceType, requestOptions = {}) =>
    downloadBlob(
      `/tenant-admin/imports/templates/${resourceType}/download`,
      `${resourceType}_import_template.xlsx`,
      requestOptions.signal,
    ),

  dryRun: (resourceType, file, requestOptions = {}) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("notify_on_completion", "true");

    return fetchJsonWithBody(`/tenant-admin/imports/${resourceType}/dry-run`, {
      method: "POST",
      body: formData,
      signal: requestOptions.signal,
      fallback: "Could not validate the import file.",
    });
  },

  confirm: async (jobId, requestOptions = {}) => {
    const result = await api.post(`/tenant-admin/imports/${jobId}/confirm`, undefined, requestOptions);
    clearDashboardMetricsCache();
    window.dispatchEvent(new Event("learnly:dashboard-cache-clear"));
    return result;
  },

  getJob: (jobId, requestOptions) => api.get(`/tenant-admin/imports/${jobId}`, requestOptions),

  listJobs: (requestOptions) => api.get("/tenant-admin/imports?limit=20", requestOptions),

  getErrors: (jobId, requestOptions) =>
    api.get(`/tenant-admin/imports/${jobId}/errors?limit=100`, requestOptions),

  downloadResult: (jobId, requestOptions = {}) =>
    downloadBlob(`/tenant-admin/imports/${jobId}/result`, `import_${jobId}_result.csv`, requestOptions.signal),

  getEmailSummary: ({ importJobId, source = "bulk_import" } = {}, requestOptions = {}) => {
    const params = new URLSearchParams();
    if (source) params.set("source", source);
    if (importJobId) params.set("import_job_id", importJobId);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return api.get(`/tenant-admin/email-outbox/summary${suffix}`, requestOptions);
  },

  recoverStaleEmails: (requestOptions) =>
    api.post("/tenant-admin/email-outbox/recover-stale", undefined, requestOptions),

  retryFailedEmails: (requestOptions) =>
    api.post("/tenant-admin/email-outbox/retry-failed", undefined, requestOptions),
};
