import { useState } from "react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import MediaImageUploader from "../../components/media/MediaImageUploader";
import Card from "../../components/ui/Card";
import Avatar from "../../components/ui/Avatar";
import ProfileCompletionForm from "../../components/shared/ProfileCompletionForm";
import { useToast } from "../../hooks/useToast";
import { authSession } from "../../services/api";
import { mediaService } from "../../services/mediaService";
import { getUserAvatarSrc, getUserDisplayName } from "../../utils/user";

function getRememberPreference() {
  return Boolean(window.localStorage.getItem("auth_user"));
}

function ProfileSettingsPage() {
  const { showSuccess } = useToast();
  const [user, setUser] = useState(() => authSession.getUser() || {});
  const role = String(user?.role || authSession.getRole() || "admin").toLowerCase();
  const displayName = getUserDisplayName(user);
  const currentAvatarUrl = getUserAvatarSrc(user);
  const canManageTenantAdminPhoto = role === "admin";

  const patchCurrentUserPhoto = (nextPhotoUrl) => {
    const nextUser = {
      ...(authSession.getUser() || user || {}),
      passport_photo_url: nextPhotoUrl || null,
    };

    authSession.setUser(nextUser, { remember: getRememberPreference() });
    setUser(nextUser);
  };

  const handlePhotoUploaded = (response) => {
    patchCurrentUserPhoto(mediaService.resolveMediaRenderUrl(response));
    showSuccess("Profile photo updated successfully.");
  };

  const handlePhotoDeleted = () => {
    patchCurrentUserPhoto(null);
    showSuccess("Profile photo removed successfully.");
  };

  return (
    <DashboardLayout
      role={role}
      title="Profile Settings"
      description="Manage the same account details used during onboarding."
    >
      <div className="mx-auto max-w-4xl space-y-5">
        <Card className="overflow-hidden">
          <div className="border-b border-border bg-surface-muted/50 p-5 sm:p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <Avatar
                name={displayName}
                user={user}
                size="xl"
                className="h-20 w-20 ring-4 ring-surface"
              />
              <div className="min-w-0">
                <p className="text-xs font-bold uppercase tracking-wide text-primary">{role} profile</p>
                <h2 className="mt-1 truncate text-xl font-semibold">{displayName || "User profile"}</h2>
                <p className="mt-1 text-sm text-text-muted">
                  Update your details and preview the passport/profile image that will appear across the workspace.
                </p>
              </div>
            </div>
          </div>

          <div className="p-5 sm:p-6">
            <ProfileCompletionForm
              role={role}
              submitLabel="Save changes"
            />
          </div>
        </Card>

        {canManageTenantAdminPhoto ? (
          <MediaImageUploader
            title="Tenant admin profile photo"
            description="Upload the admin passport/profile image used in account surfaces, cards, and authenticated workspace previews."
            variant="avatar"
            currentImageUrl={currentAvatarUrl}
            fallbackLabel={displayName}
            maxSizeBytes={2 * 1024 * 1024}
            maxSizeLabel="2 MB"
            onUpload={mediaService.uploadTenantAdminPassport}
            onDelete={() => mediaService.deleteTenantAdminPassport({ deleteObject: false })}
            onUploaded={handlePhotoUploaded}
            onDeleted={handlePhotoDeleted}
          />
        ) : null}
      </div>
    </DashboardLayout>
  );
}

export default ProfileSettingsPage;
