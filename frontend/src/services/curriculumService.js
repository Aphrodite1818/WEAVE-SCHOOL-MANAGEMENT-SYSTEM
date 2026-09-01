import { api } from "./api";

export const curriculumService = {
  getCurriculum: (levelId) =>
    api.get(`/tenant-admin/academics/levels/${levelId}/curriculum`),
  addSubject: (levelId, payload) =>
    api.post(
      `/tenant-admin/academics/levels/${levelId}/curriculum/subjects`,
      payload,
    ),
  updateSubject: (curriculumSubjectId, payload) =>
    api.patch(
      `/tenant-admin/academics/curriculum-subjects/${curriculumSubjectId}`,
      payload,
    ),
  activateSubject: (curriculumSubjectId) =>
    api.post(
      `/tenant-admin/academics/curriculum-subjects/${curriculumSubjectId}/activate`,
      {},
    ),
  deactivateSubject: (curriculumSubjectId) =>
    api.post(
      `/tenant-admin/academics/curriculum-subjects/${curriculumSubjectId}/deactivate`,
      {},
    ),
  listOfferings: (curriculumSubjectId) =>
    api.get(
      `/tenant-admin/academics/curriculum-subjects/${curriculumSubjectId}/offerings`,
    ),
  addOffering: (curriculumSubjectId, payload) =>
    api.post(
      `/tenant-admin/academics/curriculum-subjects/${curriculumSubjectId}/offerings`,
      payload,
    ),
  removeOffering: (offeringId) =>
    api.delete(`/tenant-admin/academics/curriculum-offerings/${offeringId}`),
  getClassDepartment: (classId, termId) =>
    api.get(
      `/tenant-admin/academics/classes/${classId}/terms/${termId}/department`,
    ),
  setClassDepartment: (classId, termId, academicLevelDepartmentId) =>
    api.put(
      `/tenant-admin/academics/classes/${classId}/terms/${termId}/department`,
      {
        academic_level_department_id: academicLevelDepartmentId,
      },
    ),
  clearClassDepartment: (classId, termId) =>
    api.delete(
      `/tenant-admin/academics/classes/${classId}/terms/${termId}/department`,
    ),
};
