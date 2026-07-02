import { api } from "./api";

const queryString = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const value = query.toString();
  return value ? `?${value}` : "";
};

const mergeClassSubjectPickerOptions = (classSubjectResponse, subjectResponse) => {
  const classSubjects = classSubjectResponse?.items || [];
  const subjects = subjectResponse?.items || [];
  const offeredBySubjectId = new Map(classSubjects.map((item) => [item.subject_id, item]));

  return {
    items: subjects.map((subject) => {
      const offered = offeredBySubjectId.get(subject.id);
      return offered || {
        id: subject.id,
        class_subject_id: "",
        subject_id: subject.id,
        subject_name: subject.name,
        subject_code: subject.code,
        is_core: true,
        is_active: subject.is_active !== false,
        is_offered_by_class: false,
      };
    }),
    total: subjects.length,
  };
};

export const academicService = {
  listSessions: (params) =>
    api.get(`/tenant-admin/academic/sessions${queryString(params)}`),
  createSession: (payload) => api.post("/tenant-admin/academic/sessions", payload),
  updateSession: (sessionId, payload) =>
    api.patch(`/tenant-admin/academic/sessions/${sessionId}`, payload),
  listTeacherSessions: (params) =>
    api.get(`/teachers/me/academic/sessions${queryString(params)}`),

  listTerms: (params) =>
    api.get(`/tenant-admin/academic/terms${queryString(params)}`),
  createTerm: (payload) => api.post("/tenant-admin/academic/terms", payload),
  updateTerm: (termId, payload) =>
    api.patch(`/tenant-admin/academic/terms/${termId}`, payload),
  listTeacherTerms: (params) =>
    api.get(`/teachers/me/academic/terms${queryString(params)}`),

  listGradingScales: (params) =>
    api.get(`/tenant-admin/academic/grading-scales${queryString(params)}`),
  createGradingScale: (payload) =>
    api.post("/tenant-admin/academic/grading-scales", payload),
  updateGradingScale: (scaleId, payload) =>
    api.patch(`/tenant-admin/academic/grading-scales/${scaleId}`, payload),

  listClassSubjects: (classId, params) =>
    api.get(`/classes/${classId}/subjects${queryString(params)}`),
  listClassSubjectPickerOptions: async (classId, params) => {
    const [classSubjectResponse, subjectResponse] = await Promise.all([
      api.get(`/classes/${classId}/subjects${queryString(params)}`),
      api.get(`/subjects${queryString({ is_active: true, limit: 100 })}`),
    ]);
    return mergeClassSubjectPickerOptions(classSubjectResponse, subjectResponse);
  },
  addClassSubject: (classId, payload) =>
    api.post(`/classes/${classId}/subjects`, payload),
  deactivateClassSubject: (classSubjectId) =>
    api.delete(`/class-subjects/${classSubjectId}`),

  listTeacherAssignments: (params) =>
    api.get(`/tenant-admin/academic/teacher-assignments${queryString(params)}`),
  createTeacherAssignment: (payload) =>
    api.post("/tenant-admin/academic/teacher-assignments", payload),
  deactivateTeacherAssignment: (assignmentId) =>
    api.patch(`/tenant-admin/academic/teacher-assignments/${assignmentId}/deactivate`),
  reassignTeacherAssignment: (assignmentId, payload) =>
    api.post(`/tenant-admin/academic/teacher-assignments/${assignmentId}/reassign`, payload),

  listSubjectAssignments: (params) =>
    api.get(`/tenant-admin/academic/subject-assignments${queryString(params)}`),
  createSubjectAssignment: (payload) =>
    api.post("/tenant-admin/academic/subject-assignments", payload),
  updateSubjectAssignment: (assignmentId, payload) =>
    api.patch(`/tenant-admin/academic/subject-assignments/${assignmentId}`, payload),

  listAdminResults: (params) =>
    api.get(`/tenant-admin/academic/results${queryString(params)}`),
  saveAdminResult: (payload) => api.post("/tenant-admin/academic/results", payload),
  updateResultStatus: (resultId, payload) =>
    api.patch(`/tenant-admin/academic/results/${resultId}/status` , payload),

  listMyTeacherAssignments: () => api.get("/teachers/me/academic/assignments"),
  listTeacherResults: (params) =>
    api.get(`/teachers/me/academic/results${queryString(params)}`),
  saveTeacherResult: (payload) => api.post("/teachers/me/academic/results", payload),

  listMyResults: () => api.get("/students/me/academic/results"),
  listChildResults: (studentId) =>
    api.get(`/parents/me/children/${studentId}/academic/results`),
};

export default academicService;
