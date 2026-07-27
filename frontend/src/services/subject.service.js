import { api } from "./api";

const buildSubjectQuery = ({
  skip = 0,
  limit = 100,
  isActive,
  includeArchived,
  search,
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

  return params.toString();
};

export const subjectService = {
  getSubjects: (options = {}) =>
    api.get(`/subjects?${buildSubjectQuery(options)}`),

  getSubject: (subjectId) =>
    api.get(`/subjects/${subjectId}`),

  createSubject: (data) =>
    api.post("/subjects", data),

  updateSubject: (subjectId, data) =>
    api.patch(`/subjects/${subjectId}`, data),

  activateSubject: (subjectId) =>
    api.post(`/subjects/${subjectId}/activate`),

  deactivateSubject: (subjectId) =>
    api.post(`/subjects/${subjectId}/deactivate`),

  archiveSubject: (subjectId) =>
    api.post(`/subjects/${subjectId}/archive`, {
      confirmation: "ARCHIVE_SUBJECT",
    }),

  restoreSubject: (subjectId) =>
    api.post(`/subjects/${subjectId}/restore`, {
      confirmation: "RESTORE_SUBJECT",
    }),

  deleteSubject: (subjectId) =>
    api.delete(`/subjects/${subjectId}`),
};
