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
  ...(payload.name !== undefined ? { name: payload.name } : {}),
  ...(payload.arm !== undefined ? { arm: payload.arm || null } : {}),
  ...(payload.teacher_membership_id !== undefined || payload.teacher_id !== undefined
    ? {
        teacher_membership_id:
          payload.teacher_membership_id || payload.teacher_id || null,
      }
    : {}),
});

const normalizeClassProgressionPayload = (payload = {}) => ({
  next_class_id: payload.is_terminal ? null : payload.next_class_id || null,
  is_terminal: Boolean(payload.is_terminal),
});

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

  configureClassProgression: (classId, payload) =>
    api.put(
      `/classes/${classId}/progression`,
      normalizeClassProgressionPayload(payload)
    ),

  clearClassProgression: (classId) =>
    api.post(`/classes/${classId}/progression/clear`, {
      confirmation: "CLEAR_CLASS_PROGRESSION",
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

  deleteClass: (classId) =>
    api.post(`/classes/${classId}/deactivate`, {
      confirmation: "DEACTIVATE_CLASSROOM",
    }),
};

export const attendanceService = {
  getAttendance: (options = {}) =>
    api.get(
      `/attendance?${buildQuery(options, {
        classId: "class_id",
        studentId: "student_id",
        attendanceDate: "attendance_date",
      })}`
    ),

  createAttendance: (payload) =>
    api.post("/attendance", payload),

  updateAttendance: (attendanceId, payload) =>
    api.patch(`/attendance/${attendanceId}`, payload),

  deleteAttendance: (attendanceId) =>
    api.delete(`/attendance/${attendanceId}`),
};

export const examService = {
  getExams: (options = {}) =>
    api.get(`/exams?${buildQuery(options, { classId: "class_id", subjectId: "subject_id" })}`),

  createExam: (payload) =>
    api.post("/exams", payload),

  updateExam: (examId, payload) =>
    api.patch(`/exams/${examId}`, payload),

  deleteExam: (examId) =>
    api.delete(`/exams/${examId}`),
};

export const resultService = {
  getResults: (options = {}) =>
    api.get(
      `/results?${buildQuery(options, {
        studentId: "student_id",
        classId: "class_id",
        subjectId: "subject_id",
        term: "term",
        academicSession: "academic_session",
      })}`
    ),

  createResult: (payload) =>
    api.post("/results", payload),

  updateResult: (resultId, payload) =>
    api.patch(`/results/${resultId}`, payload),

  deleteResult: (resultId) =>
    api.delete(`/results/${resultId}`),
};
