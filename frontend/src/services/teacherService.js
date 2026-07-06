import { api } from "./api";

const clampLimit = (limit) => Math.min(Math.max(Number(limit) || 100, 1), 100);

const buildTeacherQuery = ({ skip = 0, limit = 100, search } = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(skip));
  params.set("limit", String(clampLimit(limit)));
  if (search) params.set("search", search);
  return params.toString();
};

export const teacherService = {
  getTeachers: (options = {}) =>
    api.get(`/tenant-admin/teachers?${buildTeacherQuery(options)}`),

  createTeacher: (payload) =>
    api.post("/tenant-admin/teachers", payload),

  getMyTeacher: (requestOptions) =>
    api.get("/teachers/me", requestOptions),

  getMySubjects: (options = {}, requestOptions = {}) => {
    const { signal, ...queryOptions } = options;
    return api.get(
      `/teachers/me/subjects?${new URLSearchParams({
        skip: String(queryOptions.skip ?? 0),
        limit: String(clampLimit(queryOptions.limit)),
        ...(queryOptions.search ? { search: queryOptions.search } : {}),
        ...(typeof queryOptions.isActive === "boolean"
          ? { is_active: String(queryOptions.isActive) }
          : {}),
      }).toString()}`,
      {
        ...requestOptions,
        ...(signal ? { signal } : {}),
      }
    );
  },

  getTeacher: (teacherId) =>
    api.get(`/tenant-admin/teachers/${teacherId}`),

  updateTeacher: (teacherId, payload) =>
    api.patch(`/tenant-admin/teachers/${teacherId}`, payload),

  updateMyTeacherProfile: (payload) =>
    api.patch("/teachers/me/profile", payload),

  deleteTeacher: (teacherId) =>
    api.delete(`/tenant-admin/teachers/${teacherId}`),
};
