import { api } from "./api";

const buildUploadForm = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return formData;
};

const resolveMediaRenderUrl = (response) =>
  response?.render_url ||
  response?.media_asset?.cdn_url ||
  response?.media_asset?.public_url ||
  response?.media_asset?.signed_url ||
  null;

export const mediaService = {
  resolveMediaRenderUrl,

  uploadSchoolLogo: (file) =>
    api.postForm("/tenant-admin/media/school-logo", buildUploadForm(file)),

  deleteSchoolLogo: ({ deleteObject = false } = {}) =>
    api.delete(`/tenant-admin/media/school-logo?delete_object=${deleteObject}`),

  uploadStudentPassport: (studentId, file) =>
    api.postForm(
      `/tenant-admin/media/students/${studentId}/passport-photo`,
      buildUploadForm(file)
    ),

  deleteStudentPassport: (studentId, { deleteObject = false } = {}) =>
    api.delete(
      `/tenant-admin/media/students/${studentId}/passport-photo?delete_object=${deleteObject}`
    ),

  uploadTeacherPassport: (teacherId, file) =>
    api.postForm(
      `/tenant-admin/media/teachers/${teacherId}/passport-photo`,
      buildUploadForm(file)
    ),

  deleteTeacherPassport: (teacherId, { deleteObject = false } = {}) =>
    api.delete(
      `/tenant-admin/media/teachers/${teacherId}/passport-photo?delete_object=${deleteObject}`
    ),

  uploadTenantAdminPassport: (file) =>
    api.postForm("/tenant-admin/media/profile/passport-photo", buildUploadForm(file)),

  deleteTenantAdminPassport: ({ deleteObject = false } = {}) =>
    api.delete(`/tenant-admin/media/profile/passport-photo?delete_object=${deleteObject}`),

  listAssets: (params = {}) => {
    const searchParams = new URLSearchParams();

    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        searchParams.set(key, value);
      }
    });

    const query = searchParams.toString();
    return api.get(`/tenant-admin/media/assets${query ? `?${query}` : ""}`);
  },

  getAsset: (mediaAssetId) => api.get(`/tenant-admin/media/assets/${mediaAssetId}`),

  getSignedUrl: (mediaAssetId, { expiresInSeconds = 300 } = {}) =>
    api.get(
      `/tenant-admin/media/assets/${mediaAssetId}/signed-url?expires_in_seconds=${expiresInSeconds}`
    ),
};
