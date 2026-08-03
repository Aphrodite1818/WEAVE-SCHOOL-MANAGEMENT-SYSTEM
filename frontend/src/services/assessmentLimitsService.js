import { api } from "./api";

export const assessmentLimitsService = {
  getAdminLimits: () => api.get("/tenant-admin/academics/assessment-limits"),
  getTeacherLimits: () => api.get("/teachers/academics/assessment-limits"),
  getStudentLimits: () => api.get("/students/academics/assessment-limits"),
};

export default assessmentLimitsService;
