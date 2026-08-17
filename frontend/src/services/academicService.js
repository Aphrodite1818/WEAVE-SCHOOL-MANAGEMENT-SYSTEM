import { api } from "./api";

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

const stripTermCreateOnlyFields = (payload = {}) => {
  const updatablePayload = { ...payload };
  delete updatablePayload.academic_session_id;
  return updatablePayload;
};

const buildTeacherAssignmentPayload = (payload = {}) => ({
  class_id: payload.class_id,
  curriculum_subject_id: payload.curriculum_subject_id,
  academic_term_id: payload.academic_term_id,
  teacher_membership_id: payload.teacher_membership_id || payload.teacher_id,
  ...(payload.effective_from ? { effective_from: payload.effective_from } : {}),
});

const reassignTeacherAssignment = async (assignmentId, payload) => {
  const teacherMembershipId =
    payload.teacher_membership_id || payload.teacher_id;
  return api.post(
    `/tenant-admin/academics/teacher-assignments/${assignmentId}/reassign`,
    {
      teacher_membership_id: teacherMembershipId,
      ...(payload.effective_from ? { effective_from: payload.effective_from } : {}),
    },
  );
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
  getSessionDependencies: (sessionId) =>
    api.get(`/tenant-admin/academics/sessions/${sessionId}/dependencies`),
  startSessionClosing: (sessionId, payload) =>
    api.post(`/tenant-admin/academics/sessions/${sessionId}/start-closing`, {
      confirmation: "START_SESSION_CLOSING",
      ...payload,
    }),
  deleteSession: (sessionId) =>
    api.delete(`/tenant-admin/academics/sessions/${sessionId}`, {
      body: JSON.stringify({
        confirmation: "DELETE_ACADEMIC_SESSION",
      }),
      headers: { "Content-Type": "application/json" },
    }),
  listTeacherSessions: (params) =>
    api.get(`/teachers/academics/sessions${queryString(params)}`),

  listTerms: (params) =>
    api.get(`/tenant-admin/academics/terms${queryString(params)}`),
  createTerm: (payload) => api.post("/tenant-admin/academics/terms", payload),
  updateTerm: (termId, payload) =>
    api.patch(
      `/tenant-admin/academics/terms/${termId}`,
      stripTermCreateOnlyFields(payload),
    ),
  openTerm: (termId) =>
    api.post(`/tenant-admin/academics/terms/${termId}/open`, {
      confirmation: "OPEN_ACADEMIC_TERM",
    }),
  getTermDependencies: (termId) =>
    api.get(`/tenant-admin/academics/terms/${termId}/dependencies`),
  closeTerm: (termId) =>
    api.post(`/tenant-admin/academics/terms/${termId}/close`, {
      confirmation: "CLOSE_ACADEMIC_TERM",
    }),
  startTermClosing: (termId) =>
    api.post(`/tenant-admin/academics/terms/${termId}/start-closing`, {
      confirmation: "START_TERM_CLOSING",
    }),
  finalizeTermClose: (termId) =>
    api.post(`/tenant-admin/academics/terms/${termId}/finalize-close`, {
      confirmation: "FINALIZE_TERM_CLOSE",
    }),
  cancelTermClosure: (termId, reason) =>
    api.post(`/tenant-admin/academics/terms/${termId}/cancel-closure`, {
      confirmation: "CANCEL_TERM_CLOSURE",
      reason,
    }),
  deleteTerm: (termId) =>
    api.delete(`/tenant-admin/academics/terms/${termId}`, {
      body: JSON.stringify({
        confirmation: "DELETE_ACADEMIC_TERM",
      }),
      headers: { "Content-Type": "application/json" },
    }),
  listTeacherTerms: (params) =>
    api.get(`/teachers/academics/terms${queryString(params)}`),

  listAssessmentSchemes: () =>
    api.get("/tenant-admin/academics/assessment-schemes"),
  getActiveAssessmentScheme: () =>
    api.get("/tenant-admin/academics/assessment-schemes/active"),
  createAssessmentScheme: (payload) =>
    api.post("/tenant-admin/academics/assessment-schemes", payload),
  updateAssessmentScheme: (schemeId, payload) =>
    api.patch(`/tenant-admin/academics/assessment-schemes/${schemeId}`, payload),
  addAssessmentComponent: (schemeId, payload) =>
    api.post(
      `/tenant-admin/academics/assessment-schemes/${schemeId}/components`,
      payload,
    ),
  updateAssessmentComponent: (schemeId, componentId, payload) =>
    api.patch(
      `/tenant-admin/academics/assessment-schemes/${schemeId}/components/${componentId}`,
      payload,
    ),
  removeAssessmentComponent: (schemeId, componentId) =>
    api.delete(
      `/tenant-admin/academics/assessment-schemes/${schemeId}/components/${componentId}`,
    ),
  reorderAssessmentComponents: (schemeId, componentIds) =>
    api.put(
      `/tenant-admin/academics/assessment-schemes/${schemeId}/component-order`,
      { component_ids: componentIds },
    ),
  activateAssessmentScheme: (schemeId) =>
    api.post(
      `/tenant-admin/academics/assessment-schemes/${schemeId}/activate`,
      {},
    ),
  getTeacherAssessmentScheme: () =>
    api.get("/teachers/academics/assessment-scheme"),
  getStudentAssessmentScheme: () =>
    api.get("/students/academics/assessment-scheme"),

  listGradingScales: (params) =>
    api.get(`/tenant-admin/academics/grading-scales${queryString(params)}`),
  createGradingScale: (payload) =>
    api.post("/tenant-admin/academics/grading-scales", payload),
  updateGradingScale: (scaleId, payload) =>
    api.patch(`/tenant-admin/academics/grading-scales/${scaleId}`, payload),
  activateGradingScale: (scaleId) =>
    api.post(`/tenant-admin/academics/grading-scales/${scaleId}/activate`, {}),
  deactivateGradingScale: (scaleId) =>
    api.post(`/tenant-admin/academics/grading-scales/${scaleId}/deactivate`, {}),
  getGradingScaleDependencies: (scaleId) =>
    api.get(`/tenant-admin/academics/grading-scales/${scaleId}/dependencies`),
  deleteGradingScale: (scaleId) =>
    api.delete(`/tenant-admin/academics/grading-scales/${scaleId}`, {
      body: JSON.stringify({ confirmation: "DELETE_GRADING_SCALE" }),
      headers: { "Content-Type": "application/json" },
    }),
  getGradingReadiness: () =>
    api.get("/tenant-admin/academics/grading-scales/readiness-preview"),

  listTeacherAssignments: (params) =>
    api.get(
      `/tenant-admin/academics/teacher-assignments${queryString(params)}`,
    ),
  getTeacherAssignmentDependencies: (assignmentId) =>
    api.get(
      `/tenant-admin/academics/teacher-assignments/${assignmentId}/dependencies`,
    ),
  createTeacherAssignment: (payload) =>
    api.post(
      "/tenant-admin/academics/teacher-assignments",
      buildTeacherAssignmentPayload(payload),
    ),
  deactivateTeacherAssignment: (assignmentId) =>
    api.post(
      `/tenant-admin/academics/teacher-assignments/${assignmentId}/end`,
      { effective_to: new Date().toISOString().slice(0, 10) },
    ),
  endTeacherAssignment: (assignmentId, payload) =>
    api.post(
      `/tenant-admin/academics/teacher-assignments/${assignmentId}/end`,
      payload,
    ),
  deleteTeacherAssignment: (assignmentId, payload) =>
    api.delete(`/tenant-admin/academics/teacher-assignments/${assignmentId}`, {
      body: JSON.stringify({
        confirmation: "DELETE_TEACHER_ASSIGNMENT",
        ...payload,
      }),
      headers: { "Content-Type": "application/json" },
    }),
  reassignTeacherAssignment,

  listAdminResults: (params, requestOptions) =>
    api.get(
      `/tenant-admin/academics/results${queryString(params)}`,
      requestOptions,
    ),
  saveAdminResult: (payload) =>
    api.post("/tenant-admin/academics/results", payload),
  updateResultStatus: (resultId, payload) =>
    api.patch(`/tenant-admin/academics/results/${resultId}/status`, payload),
  reopenResult: (resultId, payload) =>
    api.post(`/tenant-admin/academics/results/${resultId}/reopen`, payload),

  listMyTeacherAssignments: (requestOptions) =>
    api.get("/teachers/academics/assignments", requestOptions),
  listMyAssignmentStudents: (assignmentId, params) =>
    api.get(
      `/teachers/academics/assignments/${assignmentId}/students${queryString(params)}`,
    ),
  listTeacherResults: (params, requestOptions) =>
    api.get(
      `/teachers/academics/results${queryString(params)}`,
      requestOptions,
    ),

  listMyResults: (requestOptions) =>
    api.get("/students/academics/results", requestOptions),
  listMySubjectCards: (requestOptions) =>
    api.get("/students/academics/subjects", requestOptions),
  listChildResults: (studentId, requestOptions) =>
    api.get(
      `/parents/academics/students/${studentId}/results`,
      requestOptions,
    ),
  listChildSubjectCards: (studentId, requestOptions) =>
    api.get(
      `/parents/academics/students/${studentId}/subjects`,
      requestOptions,
    ),
};

export default academicService;
