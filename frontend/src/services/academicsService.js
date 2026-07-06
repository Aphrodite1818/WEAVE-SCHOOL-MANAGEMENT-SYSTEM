import { api } from "./api";

const buildQuery = (options = {}, map = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(options.skip ?? 0));
  params.set("limit", String(options.limit ?? 100));

  Object.entries(map).forEach(([optionKey, paramKey]) => {
    if (options[optionKey]) params.set(paramKey, options[optionKey]);
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

const filterClasses = (items, search) => {
  const normalizedSearch = String(search || "").trim().toLowerCase();
  if (!normalizedSearch) return items;

  return items.filter((item) =>
    [item.name, item.level, item.arm]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(normalizedSearch))
  );
};

export const classService = {
  getClasses: async (options = {}, requestOptions = {}) => {
    const { signal, ...queryOptions } = options;
    const result = normalizeListResponse(
      await api.get(`/classes?${buildQuery(queryOptions)}`, {
        ...requestOptions,
        ...(signal ? { signal } : {}),
      })
    );
    const items = filterClasses(result.items, queryOptions.search);

    return {
      ...result,
      items,
      total: queryOptions.search ? items.length : result.total,
    };
  },

  createClass: (payload) =>
    api.post("/classes", payload),

  updateClass: (classId, payload) =>
    api.patch(`/classes/${classId}`, payload),

  deleteClass: (classId) =>
    api.delete(`/classes/${classId}`),
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
