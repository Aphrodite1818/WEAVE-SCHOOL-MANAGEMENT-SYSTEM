import { api, parseApiError } from "./api";

const NEW_CLASS_SUBJECT_PREFIX = "catalog-subject";

const queryString = (params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (key === "signal") return;
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const value = query.toString();
  return value ? `?${value}` : "";
};

const sessionPayload = (payload = {}) => ({
  ...(payload.name !== undefined ? { name: payload.name } : {}),
  ...(payload.start_date !== undefined ? { start_date: payload.start_date } : {}),
  ...(payload.end_date !== undefined ? { end_date: payload.end_date } : {}),
  ...(payload.next_academic_session_id !== undefined
    ? { next_academic_session_id: payload.next_academic_session_id }
    : {}),
});

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

const activateClassSubject = (classId, classSubjectId) =>
  api.patch(`/classes/${classId}/subjects/${classSubjectId}/activate`, {});

const resolveExistingClassSubjectId = async (classId, subjectId) => {
  const response = await api.get(`/classes/${classId}/subjects${queryString({ active_only: false, limit: 100 })}`);
  const existing = (response?.items || []).find((item) => item.subject_id === subjectId);
  if (!existing?.id) {
    throw new Error("Subject is already attached to this class, but the existing class-subject could not be loaded.");
  }

  if (existing.is_active === false) {
    const activated = await activateClassSubject(classId, existing.id);
    return activated?.id || existing.id;
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
  teacher_membership_id:
    payload.teacher_membership_id || payload.teacher_id,
  class_subject_id: classSubjectId,
});

const activateTeacherAssignment = (assignmentId) =>
  api.post(`/tenant-admin/academics/teacher-assignments/${assignmentId}/activate`);

const reassignTeacherAssignment = async (assignmentId, payload) => {
  const teacherMembershipId =
    payload.teacher_membership_id || payload.teacher_id;
  const response = await api.post(
    `/tenant-admin/academics/teacher-assignments/${assignmentId}/reassign`,
    { teacher_membership_id: teacherMembershipId },
  );

  if (
    response?.is_active === false &&
    response?.teacher_membership_id === teacherMembershipId
  ) {
    return activateTeacherAssignment(assignmentId);
  }

  return response;
};

export const academicService = {
  listSessions: (params) =>
    api.get(`/tenant-admin/academics/sessions${queryString(params)}`),
  createSession: (payload) =>
    api.post("/tenant-admin/academics/sessions", sessionPayload(payload)),
  updateSession: (sessionId, payload) =>
    api.patch(
      `/tenant-admin/academics/sessions/${sessionId}`,
      sessionPayload(payload),
    ),
  openSession: (sessionId) =>
    api.post(`/tenant-admin/academics/sessions/${sessionId}/open`, {
      confirmation: "OPEN_ACADEMIC_SESSION",
    }),
  listTeacherSessions: (params) =>
    api.get(`/teachers/academics/sessions${queryString(params)}`),

  listTerms: (params) =>
    api.get(`/tenant-admin/academics/terms${queryString(params)}`),
  createTerm: (payload) => api.post("/tenant-admin/academics/terms", payload),
  updateTerm: (termId, payload) =>
    api.patch(`/tenant-admin/academics/terms/${termId}`, stripTermCreateOnlyFields(payload)),
  listTeacherTerms: (params) =>
    api.get(`/teachers/academics/terms${queryString(params)}`),

  listGradingScales: (params) =>
    api.get(`/tenant-admin/academics/grading-scales${queryString(params)}`),
  createGradingScale: (payload) =>
    api.post("/tenant-admin/academics/grading-scales", payload),
  updateGradingScale: (scaleId, payload) =>
    api.patch(`/tenant-admin/academics/grading-scales/${scaleId}`, payload),

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
  activateClassSubject,
  deactivateClassSubject: (classSubjectId) =>
    api.delete(`/class-subjects/${classSubjectId}`),

  listTeacherAssignments: (params) =>
    api.get(`/tenant-admin/academics/teacher-assignments${queryString(params)}`),
  createTeacherAssignment: async (payload) => {
    const classSubjectId = await resolveClassSubjectId(
      payload.class_subject_id,
      payload.is_core ?? true,
    );

    return api.post(
      "/tenant-admin/academics/teacher-assignments",
      buildTeacherAssignmentPayload(payload, classSubjectId),
    );
  },
  deactivateTeacherAssignment: (assignmentId) =>
    api.post(`/tenant-admin/academics/teacher-assignments/${assignmentId}/deactivate`),
  activateTeacherAssignment,
  reassignTeacherAssignment,

  listAdminResults: (params, requestOptions) =>
    api.get(`/tenant-admin/academics/results${queryString(params)}`, requestOptions),
  saveAdminResult: (payload) => api.post("/tenant-admin/academics/results", payload),
  updateResultStatus: (resultId, payload) =>
    api.patch(`/tenant-admin/academics/results/${resultId}/status`, payload),

  listMyTeacherAssignments: (requestOptions) =>
    api.get("/teachers/academics/assignments", requestOptions),
  listMyAssignmentStudents: (assignmentId, params) =>
    api.get(`/teachers/academics/assignments/${assignmentId}/students${queryString(params)}`),
  listTeacherResults: (params, requestOptions) =>
    api.get(`/teachers/academics/results${queryString(params)}`, requestOptions),
  saveTeacherResult: (payload) => api.post("/teachers/academics/results", payload),

  listMyResults: (requestOptions) =>
    api.get("/students/academics/results", requestOptions),
  listMySubjectCards: (requestOptions) =>
    api.get("/students/academics/subjects", requestOptions),
  listChildResults: (studentId, requestOptions) =>
    api.get(`/parents/academics/students/${studentId}/results`, requestOptions),
  listChildSubjectCards: (studentId, requestOptions) =>
    api.get(`/parents/academics/students/${studentId}/subjects`, requestOptions),
};

export default academicService;
