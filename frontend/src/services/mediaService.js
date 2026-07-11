import { api } from "./api";

const buildUploadBody = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return formData;
};

export const mediaService = {
  uploadProfilePhoto(file) {
    return api.postForm("/tenant-admin/media/profile/passport-photo", buildUploadBody(file));
  },

  deleteProfilePhoto() {
    return api.delete("/tenant-admin/media/profile/passport-photo");
  },

  uploadSchoolLogo(file) {
    return api.postForm("/tenant-admin/media/school-logo", buildUploadBody(file));
  },

  deleteSchoolLogo() {
    return api.delete("/tenant-admin/media/school-logo");
  },
};
