import { api, parseApiError } from "./api";

const NEW_CLASS_SUBJECT_PREFIX = "catalog-subject";

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

const newClassSubjectValue = (classId, subjectId) =>
  `${NEW_CLASS_SUBJECT_PREFIX}:${classId}:${subjectId}`;

const parseNewClassSubjectValue = (value) => {
  if (typeof value !== "string" || !value.startsWith(`${NEW_CLASS_SUBJECT_PREFIX}:`)) {
    return null;
  }

  const [, classId, subjectId] = value.split(":");
  if (!classId || !subjectId) return null;

  return { classId, subjectId };
};

const mergeClassSubjectPickerOptions = (classId, classSubjectResponse, subjectResponse) => {
  const classSubjects = classSubjectResponse?.items || [];
  const subjects = subjectResponse?.items || [];
  const offeredBySubjectId = new Map(classSubjects.map((item) => [item.subject_id, item]));

  return {
    items: subjects.map((subject) => {
      const offered = offeredBySubjectId.get(subject.id);
      return offered || {
        id: newClassSubjectValue(classId, subject.id),
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

const resolveExistingClassSubjectId = async (classId, subjectId) => {
  const response = await api.get(`/classes/${classId}/subjects${queryString({ active_only: true, limit: 100 })}`);
  const existing = (response?.items || []).find((item) => item.subject_id === subjectId);
  if (!existing?.id) {
    throw new Error("Subject is already attached to this class, but the existing class-subject could not be loaded.");
  }
  return existing.id;
};

const resolveClassSubjectId = async (classSubjectId, isCore = true) => {
  const pending = parseNewClassSubjectValue(classSubjectId);
  if (!pending) return classSubjectId;

  try {
    const created = await api.post(`/classes/${pending.classId}/subjects`, {
      subject_id: pending.subjectId,
      is_core: isCore,
    });

    return created.id;
  } catch (error) {
    const parsed = parseApiError(error, "Could not attach subject to class.");
    if (parsed.status === 409) {
      return resolveExistingClassSubjectId(pending.classId, pending.subjectId);
    }
    throw error;
  }
};

const stripTermCreateOnlyFields = (payload = {}) => {
  const updatablePayload = { ...payload };
  delete updatablePayload.academic_session_id;
  return updatablePayload;
};

const buildTeacherAssignmentPayload = (payload = {}, classSubjectId) => ({
  teacher_id: payload.teacher_id,
  class_subject_id: classSubjectId,
});

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
    api.patch(`/tenant-admin/academic/terms/${termId}`, stripTermCreateOnlyFields(payload)),
  listTeacherTerms: (params) =>
    api.get(`/teachers/me/academic/terms${queryString(params)}`),

  listGradingScales: (params) =>
    api.get(`/tenant-admin/academic/grading-scales${queryString(params)}`),
  createGradingScale: (payload) =>
    api.post("/tenant-admin/academic/grading-scales", payload),
  updateGradingScale: (scaleId, payload) =>
    api.patch(`/tenant-admin/academic/grading-scales/${scaleId}`, payload),

  listClassSubjects: async (classId, params) => {
    const [classSubjectResponse, subjectResponse] = await Promise.all([
      api.get(`/classes/${classId}/subjects${queryString(params)}`),
      api.get(`/subjects${queryString({ is_active: true, limit: 100 })}`),
    ]);
    return mergeClassSubjectPickerOptions(classId, classSubjectResponse, subjectResponse);
  },
  listOfferedClassSubjects: (classId, params) =>
    api.get(`/classes/${classId}/subjects${queryString(params)}`),
  addClassSubject: (classId, payload) =>
    api.post(`/classes/${classId}/subjects`, payload),
  deactivateClassSubject: (classSubjectId) =>
    api.delete(`/class-subjects/${classSubjectId}`),

  listTeacherAssignments: (params) =>
    api.get(`/tenant-admin/academic/teacher-assignments${queryString(params)}`),
  createTeacherAssignment: async (payload) => {
    const classSubjectId = await resolveClassSubjectId(
      payload.class_subject_id,
      payload.is_core ?? true,
    );

    return api.post(
      "/tenant-admin/academic/teacher-assignments",
      buildTeacherAssignmentPayload(payload, classSubjectId),
    );
  },
  deactivateTeacherAssignment: (assignmentId) =>
    api.patch(`/tenant-admin/academic/teacher-assignments/${assignmentId}/deactivate`),
  reassignTeacherAssignment: (assignmentId, payload) =>
    api.post(`/tenant-admin/academic/teacher-assignments/${assignmentId}/reassign`, payload),

  listAdminResults: (params) =>
    api.get(`/tenant-admin/academic/results${queryString(params)}`),
  saveAdminResult: (payload) => api.post("/tenant-admin/academic/results", payload),
  updateResultStatus: (resultId, payload) =>
    api.patch(`/tenant-admin/academic/results/${resultId}/status`, payload),

  listMyTeacherAssignments: () => api.get("/teachers/me/academic/assignments"),
  listMyAssignmentStudents: (assignmentId, params) =>
    api.get(`/teachers/me/academic/assignments/${assignmentId}/students${queryString(params)}`),
  listTeacherResults: (params) =>
    api.get(`/teachers/me/academic/results${queryString(params)}`),
  saveTeacherResult: (payload) => api.post("/teachers/me/academic/results", payload),

  listMyResults: () => api.get("/students/me/academic/results"),
  listMySubjectCards: () => api.get("/students/me/academic/subjects"),
  listChildResults: (studentId) =>
    api.get(`/parents/me/children/${studentId}/academic/results`),
};

export default academicService;
