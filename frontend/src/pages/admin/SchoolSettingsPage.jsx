import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BellRing,
  BookOpen,
  Building2,
  CheckCircle2,
  CreditCard,
  LoaderCircle,
  MapPinned,
  Palette,
  Phone,
  ShieldCheck,
  Sparkles,
  SwatchBook,
  UserCog,
  Users,
} from "lucide-react";

import {
  DEFAULT_TENANT_BRANDING,
  TENANT_BRANDING_UPDATED_EVENT,
  applyTenantBranding,
  emitTenantBrandingUpdated,
} from "../../branding/tenantBranding";
import DashboardLayout from "../../components/layout/DashboardLayout";
import MediaImageUploader from "../../components/media/MediaImageUploader";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { useToast } from "../../hooks/useToast";
import { authSession, parseApiError, remapFieldErrors } from "../../services/api";
import { brandingService } from "../../services/brandingService";
import { mediaService } from "../../services/mediaService";
import { tenantService } from "../../services/tenant.service";
import { cn } from "../../utils/cn";
import { schoolName as resolveSchoolName } from "../../utils/user";

const sectionLinks = [
  { id: "workspace-overview", label: "Overview", eyebrow: "Start here" },
  { id: "school-profile", label: "School profile", eyebrow: "Details" },
  { id: "brand-identity", label: "Branding", eyebrow: "Identity" },
  { id: "workspace-tools", label: "Workspace tools", eyebrow: "Operations" },
];

const workspaceTools = [
  {
    title: "Edit school profile",
    description: "Update address, admission prefix, timezone, and other school-managed details.",
    to: "/profile",
    icon: UserCog,
    tone: "primary",
  },
  {
    title: "Billing and subscription",
    description: "Review plan status, invoices, and upgrade paths for the school workspace.",
    to: "/admin/billing",
    icon: CreditCard,
    tone: "warning",
  },
  {
    title: "Usage and limits",
    description: "See consumption, plan limits, and tenant-level operational signals.",
    to: "/admin/usage",
    icon: Sparkles,
    tone: "success",
  },
  {
    title: "Academic configuration",
    description: "Manage sessions, terms, grading flow, results, and other academic setup.",
    to: "/admin/academic",
    icon: BookOpen,
    tone: "accent",
  },
  {
    title: "Announcements",
    description: "Control school notices and communication surfaces used across the workspace.",
    to: "/admin/announcements",
    icon: BellRing,
    tone: "primary",
  },
  {
    title: "Create users",
    description: "Add students, teachers, and parents without leaving the settings workflow.",
    to: "/admin/create-user",
    icon: Users,
    tone: "neutral",
  },
];

function getRememberPreference() {
  return Boolean(window.localStorage.getItem("auth_user"));
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
      remember: getRememberPreference(),
    }
  );

  window.dispatchEvent(
    new CustomEvent(TENANT_BRANDING_UPDATED_EVENT, {
      detail: { logoUrl: nextLogoUrl || null },
    })
  );
}

function scrollToSection(sectionId) {
  const element = document.getElementById(sectionId);
  if (!element) return;

  element.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

function SectionPills() {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      {sectionLinks.map((section) => (
        <button
          key={section.id}
          type="button"
          onClick={() => scrollToSection(section.id)}
          className="min-w-[148px] rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-left text-white transition hover:bg-white/20"
        >
          <p className="text-[10px] font-black uppercase tracking-[0.24em] text-white/55">
            {section.eyebrow}
          </p>
          <p className="mt-1 text-sm font-semibold">{section.label}</p>
        </button>
      ))}
    </div>
  );
}

function SideNavigation() {
  return (
    <Card className="hidden p-4 xl:block xl:sticky xl:top-28">
      <p className="text-xs font-black uppercase tracking-[0.24em] text-text-faint">
        Settings map
      </p>
      <div className="mt-4 space-y-2">
        {sectionLinks.map((section) => (
          <button
            key={section.id}
            type="button"
            onClick={() => scrollToSection(section.id)}
            className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-left transition hover:border-primary/30 hover:bg-primary-soft/40"
          >
            <p className="text-[10px] font-black uppercase tracking-[0.24em] text-text-faint">
              {section.eyebrow}
            </p>
            <p className="mt-1 text-sm font-semibold text-text">{section.label}</p>
          </button>
        ))}
      </div>
    </Card>
  );
}

function StatTile({ label, value, tone = "neutral" }) {
  const toneClasses = {
    primary: "border-primary/20 bg-primary-soft/60 text-primary",
    success: "border-success/20 bg-success-soft/70 text-success",
    warning: "border-warning/30 bg-warning/10 text-warning",
    neutral: "border-border bg-surface text-text",
  };

  return (
    <div className={cn("rounded-2xl border px-4 py-4", toneClasses[tone] || toneClasses.neutral)}>
      <p className="text-[11px] font-black uppercase tracking-[0.22em] opacity-70">{label}</p>
      <p className="mt-2 text-sm font-semibold text-current">{value}</p>
    </div>
  );
}

function DetailRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-border bg-surface px-4 py-3">
      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-surface-muted text-text-soft">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <p className="text-[11px] font-black uppercase tracking-[0.22em] text-text-faint">{label}</p>
        <p className="mt-1 text-sm font-medium text-text">{value}</p>
      </div>
    </div>
  );
}

function ToolCard({ tool }) {
  const iconTone = {
    primary: "bg-primary-soft text-primary",
    success: "bg-success-soft text-success",
    warning: "bg-warning/10 text-warning",
    accent: "bg-accent-soft text-accent",
    neutral: "bg-surface-muted text-text-soft",
  };

  const Icon = tool.icon;

  return (
    <Link
      to={tool.to}
      className="group rounded-[1.5rem] border border-border bg-surface p-4 transition hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-lg"
    >
      <div className="flex items-start gap-3">
        <span className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl", iconTone[tool.tone] || iconTone.neutral)}>
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-text">{tool.title}</h3>
            <ArrowRight className="h-4 w-4 shrink-0 text-text-faint transition group-hover:translate-x-0.5 group-hover:text-primary" />
          </div>
          <p className="mt-2 text-sm leading-6 text-text-muted">{tool.description}</p>
        </div>
      </div>
    </Link>
  );
}

function buildBrandingFormState(branding) {
  return {
    brand_name: branding?.brand_name || DEFAULT_TENANT_BRANDING.brand_name,
    primary_color: branding?.primary_color || DEFAULT_TENANT_BRANDING.primary_color,
    accent_color: branding?.accent_color || DEFAULT_TENANT_BRANDING.accent_color,
    sidebar_color: branding?.sidebar_color || DEFAULT_TENANT_BRANDING.sidebar_color,
    header_color: branding?.header_color || DEFAULT_TENANT_BRANDING.header_color,
    background_color: branding?.background_color || DEFAULT_TENANT_BRANDING.background_color,
    theme_mode: branding?.theme_mode || DEFAULT_TENANT_BRANDING.theme_mode,
    is_enabled: Boolean(branding?.is_enabled),
  };
}

function getPreviewTextColor(hexColor) {
  if (!/^#[0-9A-Fa-f]{6}$/.test(hexColor || "")) {
    return "#0F172A";
  }

  const red = Number.parseInt(hexColor.slice(1, 3), 16);
  const green = Number.parseInt(hexColor.slice(3, 5), 16);
  const blue = Number.parseInt(hexColor.slice(5, 7), 16);
  const luminance = (0.2126 * red) + (0.7152 * green) + (0.0722 * blue);

  return luminance > 155 ? "#0F172A" : "#F8FAFC";
}

function BrandingColorField({
  label,
  value,
  fieldName,
  onChange,
  error,
}) {
  const colorInputValue = /^#[0-9A-Fa-f]{6}$/.test(value || "")
    ? value
    : DEFAULT_TENANT_BRANDING[fieldName];

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-text-soft">{label}</label>
      <div className="flex items-center gap-3 rounded-2xl border border-border bg-surface px-3 py-3">
        <input
          type="color"
          value={colorInputValue}
          onChange={(event) => onChange(fieldName, event.target.value.toUpperCase())}
          className="h-11 w-14 cursor-pointer rounded-xl border border-border bg-transparent p-0"
        />
        <input
          type="text"
          value={value}
          onChange={(event) => onChange(fieldName, event.target.value.toUpperCase())}
          className="input-base min-h-11"
          placeholder={DEFAULT_TENANT_BRANDING[fieldName]}
        />
      </div>
      {error ? <p className="text-xs font-medium text-error">{error}</p> : null}
    </div>
  );
}

function SchoolSettingsPage() {
  const { showSuccess, showError } = useToast();
  const user = authSession.getUser() || {};
  const [tenant, setTenant] = useState(user.tenant || null);
  const [isLoading, setIsLoading] = useState(Boolean(user.tenant_id));
  const [branding, setBranding] = useState(DEFAULT_TENANT_BRANDING);
  const [brandingForm, setBrandingForm] = useState(() =>
    buildBrandingFormState(DEFAULT_TENANT_BRANDING)
  );
  const [brandingErrors, setBrandingErrors] = useState({});
  const [isSavingBranding, setIsSavingBranding] = useState(false);
  const [error, setError] = useState(null);

  const tenantId = user?.tenant_id || user?.tenant?.id;
  const schoolName = resolveSchoolName(tenant || user);
  const logoUrl =
    tenant?.logo_url ||
    user?.tenant_logo_url ||
    user?.logo_url ||
    user?.tenant?.logo_url ||
    null;

  useEffect(() => {
    let mounted = true;

    async function loadTenant() {
      if (!tenantId) {
        if (mounted) setIsLoading(false);
        return;
      }

      if (mounted) {
        setIsLoading(true);
        setError(null);
      }

      try {
        const [tenantResult, brandingResult] = await Promise.all([
          tenantService.getTenant(tenantId),
          brandingService.getBranding(),
        ]);
        if (!mounted) return;
        setTenant(tenantResult);
        setBranding(brandingResult);
        setBrandingForm(buildBrandingFormState(brandingResult));
      } catch (err) {
        if (!mounted) return;
        const parsed = parseApiError(err, "Failed to load school settings.");
        setError(parsed.message);
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadTenant();

    return () => {
      mounted = false;
    };
  }, [tenantId]);

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

  const schoolLocation =
    [tenant?.city, tenant?.state, tenant?.country].filter(Boolean).join(", ") ||
    "Location not set yet";
  const schoolPhone = tenant?.phone || "Phone not set yet";
  const admissionPrefix = tenant?.admission_number_prefix || "Not configured";
  const workspaceState = logoUrl ? "Identity is active" : "Add a logo to personalize the workspace";
  const profileHealth =
    tenant?.address && tenant?.city && tenant?.state ? "Profile looks solid" : "Finish school profile setup";
  const brandingPreview = useMemo(
    () => ({
      ...branding,
      ...brandingForm,
    }),
    [branding, brandingForm]
  );

  const handleBrandingFieldChange = (fieldName, value) => {
    setBrandingForm((current) => ({
      ...current,
      [fieldName]: value,
    }));
    setBrandingErrors((current) => ({
      ...current,
      [fieldName]: undefined,
    }));
  };

  const handleBrandingSubmit = async (event) => {
    event.preventDefault();
    setIsSavingBranding(true);
    setBrandingErrors({});

    try {
      const payload = {
        brand_name: brandingForm.brand_name || null,
        primary_color: brandingForm.primary_color,
        accent_color: brandingForm.accent_color,
        sidebar_color: brandingForm.sidebar_color,
        header_color: brandingForm.header_color,
        background_color: brandingForm.background_color,
        theme_mode: brandingForm.theme_mode,
        is_enabled: Boolean(brandingForm.is_enabled),
      };

      const response = await brandingService.updateBranding(payload);
      setBranding(response);
      setBrandingForm(buildBrandingFormState(response));

      if (response.is_enabled) {
        applyTenantBranding(response);
      } else {
        const effectiveBranding = await brandingService.getEffectiveBranding();
        applyTenantBranding(effectiveBranding);
      }

      emitTenantBrandingUpdated({
        themeVersion: response.theme_version,
        isEnabled: response.is_enabled,
      });

      showSuccess(
        response.is_enabled
          ? "School branding saved and applied."
          : "Branding saved. Workspace theme is currently disabled."
      );
    } catch (err) {
      const parsed = parseApiError(err, "Failed to save school branding.");
      setBrandingErrors(
        remapFieldErrors(parsed.fieldErrors, {
          brand_name: "brand_name",
          primary_color: "primary_color",
          accent_color: "accent_color",
          sidebar_color: "sidebar_color",
          header_color: "header_color",
          background_color: "background_color",
          theme_mode: "theme_mode",
        })
      );
      showError(parsed.message);
    } finally {
      setIsSavingBranding(false);
    }
  };

  return (
    <DashboardLayout
      role="admin"
      title="Settings"
      description="Manage school identity, profile details, and workspace operations from one cleaner control surface."
    >
      <div className="space-y-5 sm:space-y-6">
        {error ? (
          <div className="rounded-2xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm font-medium text-warning">
            {error}
          </div>
        ) : null}

        <section className="overflow-hidden rounded-[2rem] border border-border bg-surface shadow-premium">
          <div className="bg-[radial-gradient(circle_at_top_left,_rgba(148,163,184,0.18),_transparent_36%),linear-gradient(135deg,_#0f172a_0%,_#10244c_55%,_#1d4ed8_100%)] px-4 py-5 text-white sm:px-6 sm:py-6 lg:px-7 lg:py-7">
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px] xl:items-center">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.28em] text-white/60">
                  Workspace settings
                </p>
                <h2 className="mt-3 max-w-3xl text-2xl font-black tracking-tight sm:text-3xl">
                  Keep {schoolName} organized, branded, and ready for daily operations.
                </h2>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-white/70 sm:text-base">
                  This page is now a proper settings hub: profile details, workspace identity, and the admin actions that belong in one place.
                </p>

                <div className="mt-5 grid gap-3 sm:grid-cols-3">
                  <StatTile label="Workspace" value={workspaceState} tone={logoUrl ? "success" : "warning"} />
                  <StatTile label="Profile" value={profileHealth} tone={tenant?.address ? "primary" : "warning"} />
                  <StatTile label="Admission prefix" value={admissionPrefix} tone="neutral" />
                </div>

                <div className="mt-5 xl:hidden">
                  <SectionPills />
                </div>
              </div>

              <div className="rounded-[1.75rem] border border-white/10 bg-white/10 p-4 backdrop-blur">
                <div className="flex items-center gap-3">
                  <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-[1.25rem] border border-white/10 bg-white/10">
                    {logoUrl ? (
                      <img src={logoUrl} alt="" className="h-full w-full object-contain p-2" />
                    ) : (
                      <Building2 className="h-8 w-8 text-white/80" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-black uppercase tracking-[0.24em] text-white/55">
                      Current workspace
                    </p>
                    <h3 className="mt-1 truncate text-lg font-semibold">{schoolName}</h3>
                    <p className="mt-1 text-sm text-white/70">{tenant?.email || "School email not available"}</p>
                  </div>
                </div>

                <div className="mt-4 grid gap-2">
                  <div className="rounded-2xl border border-white/10 bg-white/10 px-3 py-3 text-sm text-white/80">
                    Settings now scale down cleanly on mobile instead of collapsing into a single oversized branding screen.
                  </div>
                  <Link to="/profile" className="inline-flex items-center justify-between rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-sm font-semibold text-white transition hover:bg-white/20">
                    Open school profile
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>

        <div className="grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)]">
          <SideNavigation />

          <div className="space-y-6">
            <section id="workspace-overview">
              <Card className="overflow-hidden">
                <div className="border-b border-border bg-surface-muted/35 px-4 py-4 sm:px-5">
                  <p className="text-xs font-black uppercase tracking-[0.24em] text-text-faint">
                    Workspace overview
                  </p>
                  <h3 className="mt-2 text-lg font-semibold text-text">The essentials, without the noise</h3>
                  <p className="mt-1 text-sm leading-6 text-text-muted">
                    A normal settings page should show what matters first, not dump one customization block in isolation.
                  </p>
                </div>

                <div className="grid gap-3 p-4 sm:grid-cols-2 sm:p-5">
                  <DetailRow icon={Building2} label="School name" value={schoolName} />
                  <DetailRow icon={MapPinned} label="Location" value={schoolLocation} />
                  <DetailRow icon={Phone} label="Phone" value={schoolPhone} />
                  <DetailRow icon={ShieldCheck} label="Workspace status" value={workspaceState} />
                </div>
              </Card>
            </section>

            <section id="school-profile">
              <Card className="p-4 sm:p-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <p className="text-xs font-black uppercase tracking-[0.24em] text-text-faint">
                      School profile
                    </p>
                    <h3 className="mt-2 text-lg font-semibold text-text">Core tenant information</h3>
                    <p className="mt-1 max-w-2xl text-sm leading-6 text-text-muted">
                      School-managed details still live in the profile editor. This section keeps the important values visible and gives you a clear way to update them.
                    </p>
                  </div>

                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Link to="/profile" className="w-full sm:w-auto">
                      <Button className="w-full sm:w-auto">
                        <UserCog className="h-4 w-4" />
                        Edit profile
                      </Button>
                    </Link>
                    <Link to="/admin/academic" className="w-full sm:w-auto">
                      <Button variant="outline" className="w-full sm:w-auto">
                        <BookOpen className="h-4 w-4" />
                        Academic setup
                      </Button>
                    </Link>
                  </div>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  <DetailRow icon={Building2} label="School email" value={tenant?.email || "Not set"} />
                  <DetailRow icon={MapPinned} label="Address" value={tenant?.address || "Not set"} />
                  <DetailRow icon={Phone} label="WhatsApp bot" value={tenant?.school_bot_whatssap_number || "Not connected"} />
                  <DetailRow icon={ShieldCheck} label="Timezone and language" value={[tenant?.timezone, tenant?.language].filter(Boolean).join(" | ") || "Not set"} />
                </div>
              </Card>
            </section>

            <section id="brand-identity">
              <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
                <MediaImageUploader
                  title="School logo"
                  description="Manage the logo used across authenticated tenant workspace surfaces. A square transparent PNG or clean mark works best on mobile and sidebar layouts."
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

                <Card className="p-4 sm:p-5 xl:sticky xl:top-28 xl:self-start">
                  <div className="flex items-start gap-3">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-accent">
                      <Palette className="h-5 w-5" />
                    </span>
                    <div>
                      <p className="text-xs font-black uppercase tracking-[0.24em] text-text-faint">
                        Brand identity
                      </p>
                      <h3 className="mt-1 text-lg font-semibold text-text">Logo first, color system next</h3>
                      <p className="mt-1 text-sm leading-6 text-text-muted">
                        These controls now save to the backend branding API and apply through shared workspace theme variables instead of dead placeholder swatches.
                      </p>
                    </div>
                  </div>

                  <form className="mt-5 space-y-4" onSubmit={handleBrandingSubmit}>
                    <div className="rounded-2xl border border-border bg-surface-muted/35 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-text">Use school branding</p>
                          <p className="mt-1 text-xs leading-5 text-text-muted">
                            When enabled, tenant workspace pages use this school color system.
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            handleBrandingFieldChange("is_enabled", !brandingForm.is_enabled)
                          }
                          className={cn(
                            "inline-flex min-h-11 items-center rounded-full px-4 text-sm font-semibold transition",
                            brandingForm.is_enabled
                              ? "bg-primary text-white"
                              : "border border-border bg-surface text-text-soft"
                          )}
                        >
                          {brandingForm.is_enabled ? "Enabled" : "Disabled"}
                        </button>
                      </div>
                    </div>

                    <Input
                      label="Brand name"
                      value={brandingForm.brand_name}
                      onChange={(event) =>
                        handleBrandingFieldChange("brand_name", event.target.value)
                      }
                      error={brandingErrors.brand_name}
                      placeholder={schoolName}
                    />

                    <div className="grid gap-4 lg:grid-cols-2">
                      <BrandingColorField
                        label="Primary color"
                        value={brandingForm.primary_color}
                        fieldName="primary_color"
                        onChange={handleBrandingFieldChange}
                        error={brandingErrors.primary_color}
                      />
                      <BrandingColorField
                        label="Accent color"
                        value={brandingForm.accent_color}
                        fieldName="accent_color"
                        onChange={handleBrandingFieldChange}
                        error={brandingErrors.accent_color}
                      />
                      <BrandingColorField
                        label="Sidebar color"
                        value={brandingForm.sidebar_color}
                        fieldName="sidebar_color"
                        onChange={handleBrandingFieldChange}
                        error={brandingErrors.sidebar_color}
                      />
                      <BrandingColorField
                        label="Header color"
                        value={brandingForm.header_color}
                        fieldName="header_color"
                        onChange={handleBrandingFieldChange}
                        error={brandingErrors.header_color}
                      />
                      <BrandingColorField
                        label="Workspace background"
                        value={brandingForm.background_color}
                        fieldName="background_color"
                        onChange={handleBrandingFieldChange}
                        error={brandingErrors.background_color}
                      />
                    </div>

                    <div>
                      <label className="mb-1.5 block text-sm font-medium text-text-soft">
                        Theme mode
                      </label>
                      <select
                        value={brandingForm.theme_mode}
                        onChange={(event) =>
                          handleBrandingFieldChange("theme_mode", event.target.value)
                        }
                        className="input-base"
                      >
                        <option value="light">Light</option>
                        <option value="dark">Dark</option>
                      </select>
                      {brandingErrors.theme_mode ? (
                        <p className="mt-1.5 text-xs font-medium text-error">
                          {brandingErrors.theme_mode}
                        </p>
                      ) : null}
                    </div>

                    <div className="rounded-[1.5rem] border border-border bg-surface p-4">
                      <div className="flex items-center gap-2">
                        <SwatchBook className="h-4 w-4 text-primary" />
                        <p className="text-sm font-semibold text-text">Live preview</p>
                      </div>
                      <div className="mt-4 overflow-hidden rounded-[1.25rem] border border-border shadow-soft-card">
                        <div
                          className="border-b border-black/10 px-4 py-3"
                          style={{
                            backgroundColor: brandingPreview.header_color,
                            color: getPreviewTextColor(brandingPreview.header_color),
                          }}
                        >
                          <p className="text-[11px] font-black uppercase tracking-[0.22em] opacity-70">
                            Header
                          </p>
                          <div className="mt-2 flex items-center justify-between gap-3">
                            <p className="truncate text-sm font-semibold">
                              {brandingPreview.brand_name || schoolName}
                            </p>
                            <span className="rounded-full border border-current/15 px-2.5 py-1 text-[11px] font-semibold">
                              Dashboard
                            </span>
                          </div>
                        </div>
                        <div
                          className="grid gap-0 md:grid-cols-[11rem_minmax(0,1fr)]"
                          style={{ backgroundColor: brandingPreview.background_color }}
                        >
                          <div
                            className="px-4 py-4"
                            style={{
                              backgroundColor: brandingPreview.sidebar_color,
                              color: getPreviewTextColor(brandingPreview.sidebar_color),
                            }}
                          >
                            <p className="text-[11px] font-black uppercase tracking-[0.22em] opacity-70">
                              Sidebar
                            </p>
                            <p className="mt-2 truncate text-base font-semibold">
                              {brandingPreview.brand_name || schoolName}
                            </p>
                          </div>
                          <div className="p-3">
                            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                              {[
                                ["Primary", brandingPreview.primary_color],
                                ["Accent", brandingPreview.accent_color],
                                ["Sidebar", brandingPreview.sidebar_color],
                                ["Header", brandingPreview.header_color],
                                ["Background", brandingPreview.background_color],
                              ].map(([label, color]) => (
                                <div
                                  key={label}
                                  className="rounded-2xl border border-border bg-surface/90 p-2 backdrop-blur-sm"
                                >
                                  <div
                                    className="h-11 rounded-xl border border-black/5"
                                    style={{ backgroundColor: color }}
                                  />
                                  <p className="mt-2 text-center text-[11px] font-bold text-text-muted">
                                    {label}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div className="text-xs text-text-muted">
                        Theme version {branding.theme_version ?? 0}
                      </div>
                      <Button
                        type="submit"
                        className="w-full sm:w-auto"
                        disabled={isSavingBranding}
                      >
                        {isSavingBranding ? (
                          <>
                            <LoaderCircle className="h-4 w-4 animate-spin" />
                            Saving branding...
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="h-4 w-4" />
                            Save appearance
                          </>
                        )}
                      </Button>
                    </div>
                  </form>
                </Card>
              </div>
            </section>

            <section id="workspace-tools">
              <Card className="p-4 sm:p-5">
                <div className="flex items-start gap-3">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
                    <Sparkles className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-xs font-black uppercase tracking-[0.24em] text-text-faint">
                      Workspace tools
                    </p>
                    <h3 className="mt-1 text-lg font-semibold text-text">Related admin actions in one place</h3>
                    <p className="mt-1 text-sm leading-6 text-text-muted">
                      Instead of hiding these behind scattered nav labels, the settings page now groups the admin tasks that usually follow configuration work.
                    </p>
                  </div>
                </div>

                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  {workspaceTools.map((tool) => (
                    <ToolCard key={tool.to} tool={tool} />
                  ))}
                </div>
              </Card>
            </section>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default SchoolSettingsPage;
