import { api } from "./api";
import {
  buildChangedPatch,
  hasPatchChanges,
  mergePatchResult,
  rememberById,
  rememberRecord,
} from "./patchPayload";

const subjectsById = new Map();

const buildSubjectQuery = ({
  skip = 0,
  limit = 100,
  isActive,
  includeArchived,
  search,
  lifecycleStatus,
} = {}) => {
  const params = new URLSearchParams();

  params.set("skip", String(skip));
  params.set("limit", String(limit));

  if (typeof isActive === "boolean") {
    params.set("is_active", String(isActive));
  }

  if (typeof includeArchived === "boolean") {
    params.set("include_archived", String(includeArchived));
  }

  if (search) {
    params.set("search", search);
  }

  if (lifecycleStatus) {
    params.set("lifecycle_status", lifecycleStatus);
  }

  return params.toString();
};

export const subjectService = {
  getSubjects: async (options = {}) => {
    const response = await api.get(`/subjects?${buildSubjectQuery(options)}`);
    return rememberById(subjectsById, response);
  },

  getSubject: async (subjectId) => {
    const response = await api.get(`/subjects/${subjectId}`);
    return rememberRecord(subjectsById, response);
  },

  createSubject: async (data) => {
    const response = await api.post("/subjects", data);
    return rememberRecord(subjectsById, response);
  },

  updateSubject: async (subjectId, data) => {
    const key = String(subjectId);
    const current = subjectsById.get(key);
    const changes = buildChangedPatch(current, data);
    if (!hasPatchChanges(changes)) return current;

    const response = await api.patch(`/subjects/${subjectId}`, changes);
    subjectsById.set(key, mergePatchResult(current, changes, response));
    return response;
  },

  activateSubject: (subjectId) =>
    api.post(`/subjects/${subjectId}/activate`, {
      confirmation: "ACTIVATE_SUBJECT",
    }),

  deactivateSubject: (subjectId) =>
    api.post(`/subjects/${subjectId}/deactivate`, {
      confirmation: "DEACTIVATE_SUBJECT",
    }),

  removeSubjectFromSetup: (subjectId) =>
    api.post(`/tenant-admin/setup-assistant/subjects/${subjectId}/remove`, {}),

  archiveSubject: (subjectId) =>
    api.post(`/subjects/${subjectId}/archive`, {
      confirmation: "ARCHIVE_SUBJECT",
    }),

  restoreSubject: (subjectId) =>
    api.post(`/subjects/${subjectId}/restore`, {
      confirmation: "RESTORE_SUBJECT",
    }),

  deleteSubject: (subjectId) =>
    api.delete(`/subjects/${subjectId}`, {
      body: JSON.stringify({ confirmation: "DELETE_SUBJECT" }),
    }),
};
