import { api } from "./api";

const clampLimit = (limit) => Math.min(Math.max(Number(limit) || 50, 1), 100);

const buildStudentQuery = ({
  skip = 0,
  limit = 50,
  search,
  classId,
  status,
  includeArchived = false,
} = {}) => {
  const params = new URLSearchParams();
  params.set("skip", String(Math.max(Number(skip) || 0, 0)));
  params.set("limit", String(clampLimit(limit)));
  if (search) params.set("search", search);
  if (classId) params.set("class_id", classId);
  if (status) params.set("status", status);
  if (includeArchived) params.set("include_archived", "true");
  return params.toString();
};

export const studentService = {
  getStudents: (options = {}) =>
    api.get(`/students?${buildStudentQuery(options)}`),

  getAdminStudents: (options = {}) =>
    api.get(`/tenant-admin/students?${buildStudentQuery(options)}`),

  createStudent: (payload) =>
    api.post("/tenant-admin/students", payload),

  resetStudentAccessCode: (studentId) =>
    api.post(`/tenant-admin/students/${studentId}/access-codes`, {
      purpose: "password_reset",
    }),

  getMyStudent: (requestOptions) =>
    api.get("/students/me", requestOptions),

  getMyProgression: (requestOptions) =>
    api.get("/students/academics/progression", requestOptions),

  submitProgressionSelection: (destinationId) =>
    api.post("/students/academics/progression/selection", {
      destination_id: destinationId,
    }),

  getStudentProgression: (studentId) =>
    api.get(`/tenant-admin/academics/students/${studentId}/progression`),

  overrideProgressionSelection: (studentId, destinationId) =>
    api.put(`/tenant-admin/academics/students/${studentId}/progression/selection`, {
      destination_id: destinationId,
    }),

  placeProgressionStudent: (studentId, classroomId) =>
    api.post(`/tenant-admin/academics/students/${studentId}/progression/placement`, {
      classroom_id: classroomId,
    }),

  updateMyStudentProfile: (payload) =>
    api.patch("/students/me/profile", payload),

  changeMyPassword: (payload) =>
    api.post("/students/me/change-password", payload),

  getMyParentLinkRequests: (requestOptions) =>
    api.get("/students/me/parent-link-requests", requestOptions),

  respondToParentLinkRequest: (requestId, payload) =>
    api.post(`/students/me/parent-link-requests/${requestId}/decision`, payload),

  getMyParentLinks: (requestOptions) =>
    api.get("/students/me/parent-links", requestOptions),

  getStudent: (studentId) =>
    api.get(`/students/${studentId}`),

  getAdminStudent: (studentId) =>
    api.get(`/tenant-admin/students/${studentId}`),

  updateAdminStudent: (studentId, payload) =>
    api.patch(`/tenant-admin/students/${studentId}/profile`, payload),

  getEnrollmentHistory: (studentId) =>
    api.get(`/tenant-admin/students/${studentId}/enrollments`),

  changeStudentClass: (studentId, payload) =>
    api.post(`/tenant-admin/students/${studentId}/class-change`, payload),

  suspendStudent: (studentId, payload) =>
    api.post(`/tenant-admin/students/${studentId}/suspend`, payload),

  reinstateStudent: (studentId, payload) =>
    api.post(`/tenant-admin/students/${studentId}/reinstate`, payload),

  reinstateExpelledStudent: (studentId, payload) =>
    api.post(`/tenant-admin/students/${studentId}/reinstate-expelled`, payload),

  withdrawStudent: (studentId, payload) =>
    api.post(`/tenant-admin/students/${studentId}/withdraw`, payload),

  expelStudent: (studentId, payload) =>
    api.post(`/tenant-admin/students/${studentId}/expel`, payload),

  graduateStudent: (studentId, payload) =>
    api.post(`/tenant-admin/students/${studentId}/graduate`, payload),

  archiveStudent: (studentId, payload) =>
    api.post(`/tenant-admin/students/${studentId}/archive`, payload),

  restoreStudent: (studentId, payload) =>
    api.post(`/tenant-admin/students/${studentId}/restore`, payload),

  getHardDeleteEligibility: (studentId) =>
    api.get(`/tenant-admin/students/${studentId}/hard-delete-eligibility`),

  hardDeleteStudent: (studentId, payload) =>
    api.post(`/tenant-admin/students/${studentId}/hard-delete`, payload),

  completeStudentProfile: (studentId, payload) =>
    api.patch(`/tenant-admin/students/${studentId}/profile`, payload),

  updateParentLink: (linkId, payload) =>
    api.patch(`/tenant-admin/student-parent-links/${linkId}`, payload),
};
