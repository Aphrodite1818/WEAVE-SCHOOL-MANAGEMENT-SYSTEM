import { api } from "./api";

const buildQuery = (options = {}) => {
  const params = new URLSearchParams();
  if (options.activeOnly !== undefined) params.set("active_only", String(options.activeOnly));
  if (options.includeArchived !== undefined)
    params.set("include_archived", String(options.includeArchived));
  return params.toString();
};

export const departmentService = {
  getDepartments: (options = {}) =>
    api.get(`/tenant-admin/academics/departments?${buildQuery(options)}`),
  createDepartment: (payload) => api.post("/tenant-admin/academics/departments", payload),
  updateDepartment: (departmentId, payload) =>
    api.patch(`/tenant-admin/academics/departments/${departmentId}`, payload),
  activateDepartment: (departmentId) =>
    api.post(`/tenant-admin/academics/departments/${departmentId}/activate`, {
      confirmation: "ACTIVATE_DEPARTMENT",
    }),
  deactivateDepartment: (departmentId) =>
    api.post(`/tenant-admin/academics/departments/${departmentId}/deactivate`, {
      confirmation: "DEACTIVATE_DEPARTMENT",
    }),
  archiveDepartment: (departmentId) =>
    api.post(`/tenant-admin/academics/departments/${departmentId}/archive`, {
      confirmation: "ARCHIVE_DEPARTMENT",
    }),
  restoreDepartment: (departmentId) =>
    api.post(`/tenant-admin/academics/departments/${departmentId}/restore`, {
      confirmation: "RESTORE_DEPARTMENT",
    }),
  deleteDepartment: (departmentId) =>
    api.delete(`/tenant-admin/academics/departments/${departmentId}`, {
      body: JSON.stringify({ confirmation: "DELETE_DEPARTMENT" }),
    }),

  getLevelDepartments: (levelId, options = {}) =>
    api.get(
      `/tenant-admin/academics/academic-levels/${levelId}/departments?${buildQuery(options)}`,
    ),
  attachDepartment: (levelId, departmentId) =>
    api.post(`/tenant-admin/academics/academic-levels/${levelId}/departments`, {
      department_id: departmentId,
    }),
  activateLevelDepartment: (levelId, linkId) =>
    api.post(
      `/tenant-admin/academics/academic-levels/${levelId}/departments/${linkId}/activate`,
      { confirmation: "ACTIVATE_LEVEL_DEPARTMENT" },
    ),
  deactivateLevelDepartment: (levelId, linkId) =>
    api.post(
      `/tenant-admin/academics/academic-levels/${levelId}/departments/${linkId}/deactivate`,
      { confirmation: "DEACTIVATE_LEVEL_DEPARTMENT" },
    ),
  archiveLevelDepartment: (levelId, linkId) =>
    api.post(
      `/tenant-admin/academics/academic-levels/${levelId}/departments/${linkId}/archive`,
      { confirmation: "ARCHIVE_LEVEL_DEPARTMENT" },
    ),
  restoreLevelDepartment: (levelId, linkId) =>
    api.post(
      `/tenant-admin/academics/academic-levels/${levelId}/departments/${linkId}/restore`,
      { confirmation: "RESTORE_LEVEL_DEPARTMENT" },
    ),
  deleteLevelDepartment: (levelId, linkId) =>
    api.delete(
      `/tenant-admin/academics/academic-levels/${levelId}/departments/${linkId}`,
      { body: JSON.stringify({ confirmation: "DELETE_LEVEL_DEPARTMENT" }) },
    ),
};
