import { ArrowLeft, Building2 } from "lucide-react";
import { Link } from "react-router-dom";

import DashboardLayout from "../../components/layout/DashboardLayout";
import InstitutionTypeSetting from "../../components/settings/InstitutionTypeSetting";

export default function InstitutionTypeSettingsPage() {
  return (
    <DashboardLayout
      role="admin"
      title="Institution type"
      description="Review or change the institution family that defines the academic categories available to this school."
    >
      <div className="mx-auto w-full max-w-5xl space-y-5">
        <Link
          to="/admin/settings"
          className="inline-flex min-h-10 items-center gap-2 rounded-xl px-2 text-sm font-semibold text-text-muted transition hover:bg-surface-muted hover:text-text"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to settings
        </Link>

        <div className="rounded-2xl border border-primary/20 bg-primary/5 px-4 py-4 sm:px-5">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
              <Building2 className="h-5 w-5" />
            </span>
            <div>
              <p className="text-sm font-semibold text-text">A structural school setting</p>
              <p className="mt-1 text-sm leading-6 text-text-muted">
                This is intentionally separate from profile editing. Weave previews academic dependencies before any change and never removes protected academic evidence to force a transition.
              </p>
            </div>
          </div>
        </div>

        <InstitutionTypeSetting role="admin" />
      </div>
    </DashboardLayout>
  );
}
