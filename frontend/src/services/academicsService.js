import { api } from "./api";
import { filterClasses } from "./classSearch";

const buildQuery = (options = {}, map = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(options.skip ?? 0));
  params.set("limit", String(options.limit ?? 100));
  Object.entries(map).forEach(([key, param]) => {
    if (options[key] !== undefined && options[key] !== null && options[key] !== "") params.set(param, String(options[key]));
  });
  return params.toString();
};

const normalizeListResponse = (result) => Array.isArray(result)
  ? { items: result, total: result.length }
  : { ...result, items: Array.isArray(result?.items) ? result.items : [], total: Number.isFinite(result?.total) ? result.total : result?.items?.length ?? 0 };

const normalizeClassPayload = (payload = {}) => ({
  ...(payload.academic_level_id !== undefined ? { academic_level_id: payload.academic_level_id } : {}),
  ...(payload.arm_label_id !== undefined ? { arm_label_id: payload.arm_label_id } : {}),
  ...(payload.teacher_membership_id !== undefined || payload.teacher_id !== undefined ? { teacher_membership_id: payload.teacher_membership_id || payload.teacher_id || null } : {}),
});

export const academicLevelService = {
  getCategories: () => api.get("/academic-levels/categories"),
  getLevels: (options = {}) => api.get(`/academic-levels?${buildQuery(options, { activeOnly: "active_only", includeArchived: "include_archived" })}`),
  createLevel: (payload) => api.post("/academic-levels", payload),
  updateLevel: (levelId, payload) => api.patch(`/academic-levels/${levelId}`, payload),
  removeLevelFromSetup: (levelId) => api.post(`/tenant-admin/setup-assistant/levels/${levelId}/remove`, {}),
};

export const classService = {
  getClasses: async (options = {}, requestOptions = {}) => {
    const { signal, ...queryOptions } = options;
    const result = normalizeListResponse(await api.get(`/classes?${buildQuery(queryOptions, { activeOnly: "active_only", includeArchived: "include_archived" })}`, { ...requestOptions, ...(signal ? { signal } : {}) }));
    const items = filterClasses(result.items, queryOptions.search);
    return { ...result, items, total: queryOptions.search ? items.length : result.total };
  },
  createClass: (payload) => api.post("/classes", normalizeClassPayload(payload)),
  updateClass: (classId, payload) => api.patch(`/classes/${classId}`, normalizeClassPayload(payload)),
  activateClass: (classId) => api.post(`/classes/${classId}/activate`, { confirmation: "ACTIVATE_CLASSROOM" }),
  deactivateClass: (classId) => api.post(`/classes/${classId}/deactivate`, { confirmation: "DEACTIVATE_CLASSROOM" }),
  archiveClass: (classId) => api.post(`/classes/${classId}/archive`, { confirmation: "ARCHIVE_CLASSROOM" }),
  restoreClass: (classId) => api.post(`/classes/${classId}/restore`, { confirmation: "RESTORE_CLASSROOM" }),
  removeClassFromSetup: (classId) => api.post(`/tenant-admin/setup-assistant/classes/${classId}/remove`, {}),
};

export const departmentService = {
  getDepartments: (levelId, options = {}) => api.get(`/academic-levels/${levelId}/departments?${buildQuery(options, { activeOnly: "active_only" })}`),
  createDepartment: (levelId, payload) => api.post(`/academic-levels/${levelId}/departments`, payload),
};

export const armLabelService = {
  getArmLabels: (options = {}) => api.get(`/classes/arm-labels?${buildQuery(options, { activeOnly: "active_only", includeArchived: "include_archived" })}`),
  createArmLabel: (payload) => api.post("/classes/arm-labels", { label: payload.label }),
  updateArmLabel: (id, payload) => api.patch(`/classes/arm-labels/${id}`, payload),
  archiveArmLabel: (id) => api.post(`/classes/arm-labels/${id}/archive`, {}),
};
