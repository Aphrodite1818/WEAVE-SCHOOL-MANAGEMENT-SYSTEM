import { api } from "./api";

export const curriculumService = {
  getSpecializationWorkspace: (termId) =>
    api.get(`/tenant-admin/academics/terms/${termId}/specialization-workspace`),
  addSubjects: (levelId, payload) =>
    api.post(`/tenant-admin/academics/levels/${levelId}/curriculum/subjects/bulk`, payload),
  copyCurriculum: (levelId, sourceLevelId) =>
    api.post(`/tenant-admin/academics/levels/${levelId}/curriculum/copy`, {
      source_academic_level_id: sourceLevelId,
    }),
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
  deleteSubject: (curriculumSubjectId) =>
    api.delete(
      `/tenant-admin/academics/curriculum-subjects/${curriculumSubjectId}`,
    ),
  getEligibleClasses: (curriculumSubjectId, termId) =>
    api.get(
      `/tenant-admin/academics/curriculum-subjects/${curriculumSubjectId}/eligible-classes/${termId}`,
    ),
  getResolvedClassSubjects: (classId, termId) =>
    api.get(
      `/tenant-admin/academics/classes/${classId}/terms/${termId}/subjects`,
    ),
  createTeacherAssignmentsBulk: (payload) =>
    api.post("/tenant-admin/academics/teacher-assignments/bulk", payload),
  updateSpecializationPolicy: (levelId, termPosition) =>
    api.patch(
      `/tenant-admin/academics/levels/${levelId}/specialization-policy`,
      { specialization_required_from_term_position: termPosition },
    ),
  listClassDepartments: (termId) =>
    api.get(`/tenant-admin/academics/terms/${termId}/class-departments`),
  copyClassDepartments: (termId, sourceTermId) =>
    api.post(
      `/tenant-admin/academics/terms/${termId}/class-departments/copy`,
      { source_academic_term_id: sourceTermId },
    ),
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
