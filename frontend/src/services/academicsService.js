import { api } from "./api";
import { filterClasses } from "./classSearch";

const buildQuery = (options = {}, map = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(options.skip ?? 0));
  params.set("limit", String(options.limit ?? 100));

  Object.entries(map).forEach(([optionKey, paramKey]) => {
    if (options[optionKey] !== undefined && options[optionKey] !== null && options[optionKey] !== "") {
      params.set(paramKey, String(options[optionKey]));
    }
  });

  return params.toString();
};

const normalizeListResponse = (result) => {
  if (Array.isArray(result)) {
    return {
      items: result,
      total: result.length,
    };
  }

  return {
    ...result,
    items: Array.isArray(result?.items) ? result.items : [],
    total: Number.isFinite(result?.total) ? result.total : result?.items?.length ?? 0,
  };
};

const normalizeClassPayload = (payload = {}) => ({
  ...(payload.academic_level_id !== undefined
    ? { academic_level_id: payload.academic_level_id }
    : {}),
  ...(payload.arm !== undefined ? { arm: payload.arm } : {}),
  ...(payload.teacher_membership_id !== undefined || payload.teacher_id !== undefined
    ? {
        teacher_membership_id:
          payload.teacher_membership_id || payload.teacher_id || null,
      }
    : {}),
});

const normalizeLevelProgressionPayload = (payload = {}) => ({
  next_level_id: payload.is_terminal ? null : payload.next_level_id || null,
  is_terminal: Boolean(payload.is_terminal),
});

export const academicLevelService = {
  getLevels: (options = {}) =>
    api.get(`/academic-levels?${buildQuery(options, {
      activeOnly: "active_only",
      includeArchived: "include_archived",
    })}`),
  createLevel: (payload) => api.post("/academic-levels", payload),
  updateLevel: (levelId, payload) => api.patch(`/academic-levels/${levelId}`, payload),
  configureProgression: (levelId, payload) =>
    api.put(`/academic-levels/${levelId}/progression`, normalizeLevelProgressionPayload(payload)),
  removeLevelFromSetup: (levelId) =>
    api.post(`/tenant-admin/setup-assistant/levels/${levelId}/remove`, {}),
};

export const classService = {
  getClasses: async (options = {}, requestOptions = {}) => {
    const { signal, ...queryOptions } = options;
    const result = normalizeListResponse(
      await api.get(
        `/classes?${buildQuery(queryOptions, {
          activeOnly: "active_only",
          includeArchived: "include_archived",
        })}`,
        {
          ...requestOptions,
          ...(signal ? { signal } : {}),
        }
      )
    );
    const items = filterClasses(result.items, queryOptions.search);

    return {
      ...result,
      items,
      total: queryOptions.search ? items.length : result.total,
    };
  },

  createClass: (payload) =>
    api.post("/classes", normalizeClassPayload(payload)),

  updateClass: (classId, payload) =>
    api.patch(`/classes/${classId}`, normalizeClassPayload(payload)),

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

  deleteClass: (classId) =>
    api.post(`/classes/${classId}/deactivate`, {
      confirmation: "DEACTIVATE_CLASSROOM",
    }),

  removeClassFromSetup: (classId) =>
    api.post(`/tenant-admin/setup-assistant/classes/${classId}/remove`, {}),
};

