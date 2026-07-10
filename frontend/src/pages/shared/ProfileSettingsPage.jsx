import DashboardLayout from "../../components/layout/DashboardLayout";
import Card from "../../components/ui/Card";
import Avatar from "../../components/ui/Avatar";
import ProfileCompletionForm from "../../components/shared/ProfileCompletionForm";
import { authSession } from "../../services/api";
import { getUserDisplayName } from "../../utils/user";

function ProfileSettingsPage() {
  const user = authSession.getUser();
  const role = String(user?.role || authSession.getRole() || "admin").toLowerCase();
  const displayName = getUserDisplayName(user);

  return (
    <DashboardLayout
      role={role}
      title="Profile Settings"
      description="Manage the same account details used during onboarding."
    >
      <Card className="mx-auto max-w-3xl overflow-hidden">
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
    </DashboardLayout>
  );
}

export default ProfileSettingsPage;
