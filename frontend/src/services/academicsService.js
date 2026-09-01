import { api } from "./api";
import { filterClasses } from "./classSearch";
import {
  buildChangedPatch,
  hasPatchChanges,
  mergePatchResult,
  rememberById,
  rememberRecord,
} from "./patchPayload";

const academicLevelsById = new Map();
const classesById = new Map();
const armLabelsById = new Map();

const buildQuery = (options = {}, map = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(options.skip ?? 0));
  params.set("limit", String(options.limit ?? 100));
  Object.entries(map).forEach(([key, param]) => {
    const value = options[key] ?? options[param];
    if (value !== undefined && value !== null && value !== "")
      params.set(param, String(value));
  });
  return params.toString();
};

const normalizeListResponse = (result) =>
  Array.isArray(result)
    ? { items: result, total: result.length }
    : {
        ...result,
        items: Array.isArray(result?.items) ? result.items : [],
        total: Number.isFinite(result?.total)
          ? result.total
          : (result?.items?.length ?? 0),
      };

const normalizeClassPayload = (payload = {}) => ({
  ...(payload.academic_level_id !== undefined
    ? { academic_level_id: payload.academic_level_id }
    : {}),
  ...(payload.arm_label_id !== undefined
    ? { arm_label_id: payload.arm_label_id }
    : {}),
  ...(payload.teacher_membership_id !== undefined ||
  payload.teacher_id !== undefined
    ? {
        teacher_membership_id:
          payload.teacher_membership_id || payload.teacher_id || null,
      }
    : {}),
});

const patchRemembered = async ({ cache, id, payload, request }) => {
  const key = String(id);
  const current = cache.get(key);
  const changes = buildChangedPatch(current, payload);
  if (!hasPatchChanges(changes)) return current;

  const response = await request(changes);
  cache.set(key, mergePatchResult(current, changes, response));
  return response;
};

export const academicLevelService = {
  getCategories: () => api.get("/academic-levels/categories"),
  getLevels: async (options = {}) => {
    const response = await api.get(
      `/academic-levels?${buildQuery(options, { activeOnly: "active_only", includeArchived: "include_archived" })}`,
    );
    return rememberById(academicLevelsById, response);
  },
  createLevel: async (payload) => {
    const response = await api.post("/academic-levels", payload);
    return rememberRecord(academicLevelsById, response);
  },
  updateLevel: (levelId, payload) =>
    patchRemembered({
      cache: academicLevelsById,
      id: levelId,
      payload,
      request: (changes) => api.patch(`/academic-levels/${levelId}`, changes),
    }),
  activateLevel: (levelId) => api.post(`/academic-levels/${levelId}/activate`, {}),
  deactivateLevel: (levelId) =>
    api.post(`/academic-levels/${levelId}/deactivate`, {}),
  archiveLevel: (levelId) => api.post(`/academic-levels/${levelId}/archive`, {}),
  restoreLevel: (levelId) => api.post(`/academic-levels/${levelId}/restore`, {}),
  removeLevelFromSetup: (levelId) =>
    api.post(`/tenant-admin/setup-assistant/levels/${levelId}/remove`, {}),
};

export const classService = {
  getClasses: async (options = {}, requestOptions = {}) => {
    const { signal, ...queryOptions } = options;
    const result = normalizeListResponse(
      await api.get(
        `/classes?${buildQuery(queryOptions, { activeOnly: "active_only", includeArchived: "include_archived" })}`,
        { ...requestOptions, ...(signal ? { signal } : {}) },
      ),
    );
    rememberById(classesById, result);
    const items = filterClasses(result.items, queryOptions.search);
    return {
      ...result,
      items,
      total: queryOptions.search ? items.length : result.total,
    };
  },
  createClass: async (payload) => {
    const response = await api.post(
      "/classes",
      normalizeClassPayload(payload),
    );
    return rememberRecord(classesById, response);
  },
  updateClass: (classId, payload) =>
    patchRemembered({
      cache: classesById,
      id: classId,
      payload: normalizeClassPayload(payload),
      request: (changes) => api.patch(`/classes/${classId}`, changes),
    }),
  activateClass: (classId) =>
    api.post(`/classes/${classId}/activate`, {
      confirmation: "ACTIVATE_CLASSROOM",
    }),
  deactivateClass: (classId) =>
    api.post(`/classes/${classId}/deactivate`, {
      confirmation: "DEACTIVATE_CLASSROOM",
    }),
  archiveClass: (classId) =>
    api.post(`/classes/${classId}/archive`, {
      confirmation: "ARCHIVE_CLASSROOM",
    }),
  restoreClass: (classId) =>
    api.post(`/classes/${classId}/restore`, {
      confirmation: "RESTORE_CLASSROOM",
    }),
  removeClassFromSetup: (classId) =>
    api.post(`/tenant-admin/setup-assistant/classes/${classId}/remove`, {}),
};

export const departmentService = {
  getDepartments: (levelId, options = {}) =>
    api.get(
      `/academic-levels/${levelId}/departments?${buildQuery(options, { activeOnly: "active_only", includeArchived: "include_archived" })}`,
    ),
  createDepartment: (levelId, payload) =>
    api.post(`/academic-levels/${levelId}/departments`, payload),
  updateDepartment: (levelId, departmentId, payload) =>
    api.patch(`/academic-levels/${levelId}/departments/${departmentId}`, payload),
  activateDepartment: (levelId, departmentId) =>
    api.post(`/academic-levels/${levelId}/departments/${departmentId}/activate`, {
      confirmation: "ACTIVATE_DEPARTMENT",
    }),
  deactivateDepartment: (levelId, departmentId) =>
    api.post(`/academic-levels/${levelId}/departments/${departmentId}/deactivate`, {
      confirmation: "DEACTIVATE_DEPARTMENT",
    }),
  archiveDepartment: (levelId, departmentId) =>
    api.post(`/academic-levels/${levelId}/departments/${departmentId}/archive`, {
      confirmation: "ARCHIVE_DEPARTMENT",
    }),
  restoreDepartment: (levelId, departmentId) =>
    api.post(`/academic-levels/${levelId}/departments/${departmentId}/restore`, {
      confirmation: "RESTORE_DEPARTMENT",
    }),
};

export const armLabelService = {
  getArmLabels: async (options = {}) => {
    const response = await api.get(
      `/classes/arm-labels?${buildQuery(options, { activeOnly: "active_only", includeArchived: "include_archived" })}`,
    );
    return rememberById(armLabelsById, response);
  },
  createArmLabel: async (payload) => {
    const response = await api.post("/classes/arm-labels", {
      label: payload.label,
    });
    return rememberRecord(armLabelsById, response);
  },
  updateArmLabel: (id, payload) =>
    patchRemembered({
      cache: armLabelsById,
      id,
      payload,
      request: (changes) => api.patch(`/classes/arm-labels/${id}`, changes),
    }),
  activateArmLabel: (id) =>
    api.post(`/classes/arm-labels/${id}/activate`, {
      confirmation: "ACTIVATE_ARM_LABEL",
    }),
  deactivateArmLabel: (id) =>
    api.post(`/classes/arm-labels/${id}/deactivate`, {
      confirmation: "DEACTIVATE_ARM_LABEL",
    }),
  archiveArmLabel: (id) =>
    api.post(`/classes/arm-labels/${id}/archive`, {
      confirmation: "ARCHIVE_ARM_LABEL",
    }),
  restoreArmLabel: (id) =>
    api.post(`/classes/arm-labels/${id}/restore`, {
      confirmation: "RESTORE_ARM_LABEL",
    }),
};
