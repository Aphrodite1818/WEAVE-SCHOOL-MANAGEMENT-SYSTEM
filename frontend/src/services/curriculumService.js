import { api } from "./api";

export const curriculumService = {
  getCurriculum: (levelId) => api.get(`/tenant-admin/academics/levels/${levelId}/curriculum`),
  addSubject: (levelId, payload) => api.post(`/tenant-admin/academics/levels/${levelId}/curriculum/subjects`, payload),
  updateSubject: (curriculumSubjectId, payload) => api.patch(`/tenant-admin/academics/curriculum-subjects/${curriculumSubjectId}`, payload),
  listOfferings: (curriculumSubjectId) => api.get(`/tenant-admin/academics/curriculum-subjects/${curriculumSubjectId}/offerings`),
  addOffering: (curriculumSubjectId, payload) => api.post(`/tenant-admin/academics/curriculum-subjects/${curriculumSubjectId}/offerings`, payload),
  setClassDepartment: (classId, termId, departmentId) => api.put(`/tenant-admin/academics/classes/${classId}/terms/${termId}/department`, { department_id: departmentId }),
  clearClassDepartment: (classId, termId) => api.delete(`/tenant-admin/academics/classes/${classId}/terms/${termId}/department`),
};
