import { useCallback, useEffect, useMemo, useState } from "react";
import { Building2, Image, Palette, ShieldCheck, Sparkles } from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import MediaImageUploader from "../../components/media/MediaImageUploader";
import Card from "../../components/ui/Card";
import { useToast } from "../../hooks/useToast";
import { authSession, parseApiError } from "../../services/api";
import { mediaService } from "../../services/mediaService";
import { tenantService } from "../../services/tenant.service";
import { cn } from "../../utils/cn";
import { schoolName as resolveSchoolName } from "../../utils/user";

const TENANT_BRAND_EVENT = "learnly:tenant-brand-updated";

const BRAND_STEPS = [
  {
    title: "Upload logo",
    description: "Use a clean school mark that can sit well inside the sidebar and reports.",
    icon: Image,
  },
  {
    title: "Keep contrast readable",
    description: "Brand color application is intentionally controlled so the app stays accessible.",
    icon: ShieldCheck,
  },
  {
    title: "Apply to workspace",
    description: "Authenticated school pages can inherit the brand without affecting public Learnly pages.",
    icon: Sparkles,
  },
];

function BrandStep({ step, index }) {
  const Icon = step.icon;

  return (
    <div className="rounded-3xl border border-border bg-surface/80 p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary ring-1 ring-primary/10">
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <p className="text-xs font-black uppercase tracking-[0.22em] text-text-faint">Step {index + 1}</p>
          <h3 className="mt-1 font-semibold text-text">{step.title}</h3>
          <p className="mt-1 text-sm leading-6 text-text-muted">{step.description}</p>
        </div>
      </div>
    </div>
  );
}

function WorkspacePreview({ schoolName, logoUrl }) {
  return (
    <div className="overflow-hidden rounded-[2rem] border border-border bg-surface shadow-premium">
      <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-primary px-4 py-5 text-white sm:px-5">
        <div className="flex items-center gap-3">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-white/15 bg-white/10 shadow-lg backdrop-blur">
            {logoUrl ? (
              <img src={logoUrl} alt="" className="h-full w-full object-contain p-2" />
            ) : (
              <Building2 className="h-7 w-7 text-white/85" />
            )}
          </div>
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.24em] text-white/60">Workspace preview</p>
            <h2 className="mt-1 truncate text-xl font-black sm:text-2xl">{schoolName}</h2>
          </div>
        </div>
      </div>

      <div className="grid gap-3 p-4 sm:grid-cols-3 sm:p-5">
        {["Dashboard", "Academic Hub", "Reports"].map((label, index) => (
          <div
            key={label}
            className={cn(
              "rounded-2xl border p-3 text-sm font-semibold",
              index === 0
                ? "border-primary/25 bg-primary-soft text-primary"
                : "border-border bg-surface-muted/50 text-text-soft"
            )}
          >
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}

function updateStoredTenantLogo(nextLogoUrl) {
  const currentUser = authSession.getUser() || {};
  const nextTenant = {
    ...(currentUser.tenant || {}),
    logo_url: nextLogoUrl || null,
  };

  authSession.setUser(
    {
      ...currentUser,
      tenant_logo_url: nextLogoUrl || null,
      logo_url: nextLogoUrl || null,
      tenant: nextTenant,
    },
    {
      remember: Boolean(window.localStorage.getItem("auth_user")),
    }
  );

  window.dispatchEvent(
    new CustomEvent(TENANT_BRAND_EVENT, {
      detail: { logoUrl: nextLogoUrl || null },
    })
  );
}

export default function SchoolCustomizationPage() {
  const { showSuccess } = useToast();
  const user = authSession.getUser() || {};
  const [tenant, setTenant] = useState(user.tenant || null);
  const [isLoading, setIsLoading] = useState(Boolean(user.tenant_id));
  const [error, setError] = useState(null);

  const tenantId = user?.tenant_id || user?.tenant?.id;
  const schoolName = useMemo(
    () => resolveSchoolName(tenant || user),
    [tenant, user]
  );
  const logoUrl =
    tenant?.logo_url ||
    user?.tenant_logo_url ||
    user?.logo_url ||
    user?.tenant?.logo_url ||
    null;

  const loadTenant = useCallback(async () => {
    if (!tenantId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const result = await tenantService.getTenant(tenantId);
      setTenant(result);
    } catch (err) {
      const parsed = parseApiError(err, "Failed to load school profile.");
      setError(parsed.message);
    } finally {
      setIsLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    loadTenant();
  }, [loadTenant]);

  const handleLogoUploaded = (response) => {
    const nextLogoUrl = mediaService.resolveMediaRenderUrl(response);
    setTenant((current) => ({ ...(current || {}), logo_url: nextLogoUrl }));
    updateStoredTenantLogo(nextLogoUrl);
    showSuccess("School logo updated successfully.");
  };

  const handleLogoDeleted = () => {
    setTenant((current) => ({ ...(current || {}), logo_url: null }));
    updateStoredTenantLogo(null);
    showSuccess("School logo removed successfully.");
  };

  return (
    <DashboardLayout
      role="admin"
      title="School Customization"
      description="Configure the visual identity tenants see inside the authenticated school workspace."
    >
      <div className="space-y-5 sm:space-y-6">
        {error ? (
          <div className="rounded-2xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm font-medium text-warning">
            {error}
          </div>
        ) : null}

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-5">
            <Card className="overflow-hidden border-primary/10 bg-gradient-to-br from-surface via-surface to-primary-soft/30">
              <div className="p-5 sm:p-6 lg:p-7">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div className="min-w-0">
                    <p className="text-xs font-black uppercase tracking-[0.28em] text-primary">Brand studio</p>
                    <h2 className="mt-2 text-2xl font-black tracking-tight text-text sm:text-3xl">
                      Make {schoolName} feel like home.
                    </h2>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">
                      Start with the school logo. The layout is built to stay smooth on mobile and safe for dashboards, reports, and navigation surfaces.
                    </p>
                  </div>
                  <div className="rounded-3xl border border-border bg-surface/80 p-4 text-sm shadow-sm lg:w-64">
                    <p className="font-semibold text-text">Customization status</p>
                    <p className="mt-1 text-text-muted">
                      {logoUrl ? "Logo active. Brand color routing can be added after the branding API is exposed." : "No logo yet. Upload one to personalize the workspace."}
                    </p>
                  </div>
                </div>
              </div>
            </Card>

            <MediaImageUploader
              title="School logo"
              description="Upload the logo shown in tenant workspace surfaces. Use a transparent PNG/WebP or a clean square mark for the best result."
              variant="logo"
              currentImageUrl={logoUrl}
              fallbackLabel={schoolName}
              maxSizeBytes={1 * 1024 * 1024}
              maxSizeLabel="1 MB"
              disabled={isLoading}
              onUpload={mediaService.uploadSchoolLogo}
              onDelete={() => mediaService.deleteSchoolLogo({ deleteObject: false })}
              onUploaded={handleLogoUploaded}
              onDeleted={handleLogoDeleted}
            />
          </div>

          <div className="space-y-5 xl:sticky xl:top-28 xl:self-start">
            <WorkspacePreview schoolName={schoolName} logoUrl={logoUrl} />

            <Card className="p-4 sm:p-5">
              <div className="flex items-center gap-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-accent-soft text-accent">
                  <Palette className="h-5 w-5" />
                </span>
                <div>
                  <h3 className="font-bold text-text">Brand color controls</h3>
                  <p className="text-sm text-text-muted">Prepared for the tenant branding API.</p>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2">
                {[
                  ["Primary", "bg-primary"],
                  ["Accent", "bg-accent"],
                  ["Sidebar", "bg-slate-950"],
                ].map(([label, colorClass]) => (
                  <div key={label} className="rounded-2xl border border-border bg-surface-muted/50 p-2">
                    <div className={cn("h-10 rounded-xl", colorClass)} />
                    <p className="mt-2 text-center text-[11px] font-bold text-text-muted">{label}</p>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </section>

        <section className="grid gap-3 md:grid-cols-3">
          {BRAND_STEPS.map((step, index) => (
            <BrandStep key={step.title} step={step} index={index} />
          ))}
        </section>
      </div>
    </DashboardLayout>
  );
}
