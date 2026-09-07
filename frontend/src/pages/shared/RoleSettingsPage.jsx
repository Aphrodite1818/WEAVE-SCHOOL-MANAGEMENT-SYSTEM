import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Accessibility,
  Building2,
  ChevronDown,
  ChevronRight,
  Compass,
  Eye,
  IdCard,
  Languages,
  Mail,
  Moon,
  Palette,
  ShieldCheck,
  Sun,
  UserRound,
} from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Avatar from "../../components/ui/Avatar";
import Card from "../../components/ui/Card";
import { authSession } from "../../services/api";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { FEATURE_CODES } from "../../features/subscriptions/subscriptionConfig";
import {
  requestWorkspaceTour,
  tourKeyForRole,
} from "../../features/guides/workspaceTourState";
import {
  applyAccessibilityPreferences,
  getSavedAccessibilityPreferences,
  saveAccessibilityPreferences,
} from "../../utils/accessibilityPreferences";
import { cn } from "../../utils/cn";
import { getUserDisplayName } from "../../utils/user";

const roleCopy = {
  admin: { title: "Settings", description: "Manage profile, school, guidance, and device accessibility settings." },
  teacher: { title: "Settings", description: "Manage teacher profile, workspace guidance, and device accessibility preferences." },
  student: { title: "Settings", description: "Manage student profile, workspace guidance, and device accessibility preferences." },
  parent: { title: "Settings", description: "Manage parent profile, workspace guidance, and device accessibility preferences." },
};

const themeOptions = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Eye },
];

const resolveCurrentEmail = (user) => user?.email || user?.email_address || user?.account_email || "";
const resolveAdmissionNumber = (user) => user?.admission_number || user?.student?.admission_number || user?.profile?.admission_number || "";
const resolveInstitutionType = (user) =>
  user?.institution_type ||
  user?.tenant?.institution_type ||
  user?.tenant?.tenant?.institution_type ||
  "";
const institutionTypeLabel = (value) => {
  if (value === "PRIMARY_SCHOOL") return "Primary School";
  if (value === "SECONDARY_SCHOOL") return "Secondary School";
  return "Not set";
};

function SettingsGroup({ title, children }) {
  return (
    <section className="space-y-2">
      <h2 className="px-1 text-xs font-bold uppercase tracking-wide text-text-muted sm:text-sm">{title}</h2>
      <Card className="overflow-hidden rounded-[1.35rem] border-border/80 p-0 shadow-sm">{children}</Card>
    </section>
  );
}

function SettingsRow({ icon: Icon, label, value, description, to, onClick, actionLabel }) {
  const content = (
    <div className="flex min-h-[3.75rem] items-center gap-3 border-t border-border/70 px-4 py-3 first:border-t-0 sm:px-5">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-muted text-text-soft"><Icon className="h-[18px] w-[18px]" /></span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-text sm:text-base">{label}</p>
        {description ? <p className="mt-0.5 text-xs leading-5 text-text-muted">{description}</p> : null}
      </div>
      {value ? <p className="max-w-[42%] truncate text-right text-sm text-text-muted">{value}</p> : null}
      {actionLabel ? <span className="shrink-0 text-xs font-semibold text-primary">{actionLabel}</span> : null}
      {to ? <ChevronRight className="h-4 w-4 shrink-0 text-text-faint" /> : null}
    </div>
  );

  if (to) {
    return <Link to={to} className="block transition hover:bg-surface-muted/45">{content}</Link>;
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className="block w-full text-left transition hover:bg-surface-muted/45">
        {content}
      </button>
    );
  }
  return content;
}

function ExpandableSettingsRow({ icon: Icon, label, value, open, onToggle, children }) {
  return (
    <div className="border-t border-border/70 first:border-t-0">
      <button type="button" onClick={onToggle} className="flex min-h-[3.75rem] w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-surface-muted/45 sm:px-5" aria-expanded={open}>
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-muted text-text-soft"><Icon className="h-[18px] w-[18px]" /></span>
        <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-text sm:text-base">{label}</p>{value ? <p className="mt-0.5 truncate text-xs text-text-muted">{value}</p> : null}</div>
        {open ? <ChevronDown className="h-4 w-4 shrink-0 text-text-faint" /> : <ChevronRight className="h-4 w-4 shrink-0 text-text-faint" />}
      </button>
      {open ? <div className="border-t border-border/60 px-4 py-4 sm:px-5">{children}</div> : null}
    </div>
  );
}

function ToggleRow({ label, checked, onChange }) {
  return (
    <button type="button" onClick={() => onChange(!checked)} className="flex w-full items-center justify-between rounded-xl py-1 text-left">
      <span className="text-sm font-medium text-text-soft">{label}</span>
      <span className={cn("relative h-6 w-11 rounded-full transition", checked ? "bg-primary" : "bg-border")}><span className={cn("absolute top-1 h-4 w-4 rounded-full bg-white shadow-sm transition", checked ? "left-6" : "left-1")} /></span>
    </button>
  );
}

function RoleSettingsPage({ role }) {
  const normalizedRole = String(role || "admin").toLowerCase();
  const user = authSession.getUser() || {};
  const { getFeatureGuard } = useSubscription();
  const tenantBrandingGuard = getFeatureGuard(FEATURE_CODES.TENANT_BRANDING);
  const copy = roleCopy[normalizedRole] || roleCopy.admin;
  const isStudent = normalizedRole === "student";
  const displayName = getUserDisplayName(user);
  const currentEmail = resolveCurrentEmail(user);
  const admissionNumber = resolveAdmissionNumber(user);
  const currentInstitutionType = resolveInstitutionType(user);
  const supportsWorkspaceTour = Boolean(tourKeyForRole(normalizedRole));
  const [preferences, setPreferences] = useState(() => getSavedAccessibilityPreferences());
  const [accessibilityStatus, setAccessibilityStatus] = useState("");
  const [openPanel, setOpenPanel] = useState("");
  const profileSummary = [user?.role || normalizedRole, user?.class_name || user?.student_class || user?.specialization || user?.school_name || user?.tenant?.name].filter(Boolean).join(" / ");

  const updatePreference = (patch) => {
    const nextPreferences = { ...preferences, ...patch };
    setPreferences(nextPreferences);
    applyAccessibilityPreferences(nextPreferences);
    saveAccessibilityPreferences(nextPreferences);
    setAccessibilityStatus("Preferences saved on this device.");
  };
  const togglePanel = (panel) => setOpenPanel((current) => (current === panel ? "" : panel));

  return (
    <DashboardLayout role={normalizedRole} title={copy.title} description={copy.description}>
      <div className="mx-auto grid w-full max-w-6xl gap-5 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <Card className="overflow-hidden rounded-[1.5rem] p-0">
            <div className="flex flex-col items-center border-b border-border/70 bg-surface-muted/30 px-5 py-6 text-center">
              <Avatar name={displayName} user={user} size="xl" className="h-20 w-20 ring-4 ring-surface" />
              <h2 className="mt-3 max-w-full truncate text-lg font-bold text-text">{displayName || "Your account"}</h2>
              <p className="mt-1 max-w-full truncate text-sm text-text-muted">{profileSummary || normalizedRole}</p>
            </div>
            <div className="p-2">
              <Link to="/profile" className="flex items-center justify-between rounded-2xl px-3 py-3 text-sm font-semibold text-text-soft transition hover:bg-surface-muted hover:text-text">Profile details<ChevronRight className="h-4 w-4" /></Link>
              <a href="#account" className="flex items-center justify-between rounded-2xl px-3 py-3 text-sm font-semibold text-text-soft transition hover:bg-surface-muted hover:text-text">Account<ChevronRight className="h-4 w-4" /></a>
            </div>
          </Card>
        </aside>

        <div className="space-y-5 pb-24 md:pb-0">
          <SettingsGroup title="Account">
            {isStudent ? <SettingsRow icon={IdCard} label="Admission number" value={admissionNumber || "Not assigned"} /> : <SettingsRow icon={Mail} label="Email" value={currentEmail || "No email on file"} />}
            <SettingsRow icon={UserRound} label="Profile" value={profileSummary || "Details and photo"} to="/profile" />
          </SettingsGroup>

          {normalizedRole === "admin" ? (
            <SettingsGroup title="School">
              <SettingsRow
                icon={Building2}
                label="Institution type"
                value={institutionTypeLabel(currentInstitutionType)}
                description="Review the current school structure or start a controlled institution-type change."
                to="/admin/settings/institution-type"
              />
              {tenantBrandingGuard.allowed && !tenantBrandingGuard.pending ? (
                <SettingsRow icon={Palette} label="School branding" description="Manage the shared school identity and colour palette." to="/admin/settings/branding" />
              ) : null}
            </SettingsGroup>
          ) : null}

          {supportsWorkspaceTour ? (
            <SettingsGroup title="Guidance">
              <SettingsRow
                icon={Compass}
                label="Workspace tour"
                description="Replay the introduction using only features currently available in this workspace."
                actionLabel="Replay"
                onClick={() => requestWorkspaceTour(normalizedRole)}
              />
            </SettingsGroup>
          ) : null}

          <SettingsGroup title="Appearance and accessibility">
            <ExpandableSettingsRow icon={Accessibility} label="Appearance" value={preferences.theme === "system" ? "System device preference" : preferences.theme} open={openPanel === "appearance"} onToggle={() => togglePanel("appearance")}>
              <div className="grid grid-cols-3 gap-2">
                {themeOptions.map((item) => {
                  const Icon = item.icon;
                  const active = preferences.theme === item.value;
                  return <button key={item.value} type="button" onClick={() => updatePreference({ theme: item.value })} className={cn("flex min-h-10 items-center justify-center gap-1.5 rounded-xl border px-2 text-xs font-bold transition sm:text-sm", active ? "is-selected-highlight" : "border-border bg-surface text-text-soft hover:bg-surface-muted")}><Icon className="h-4 w-4" />{item.label}</button>;
                })}
              </div>
            </ExpandableSettingsRow>
            <ExpandableSettingsRow icon={Eye} label="Font size" value={`${preferences.fontScale}%`} open={openPanel === "font"} onToggle={() => togglePanel("font")}>
              <input className="w-full accent-primary" type="range" min="90" max="115" step="5" value={preferences.fontScale} onChange={(event) => updatePreference({ fontScale: Number(event.target.value) })} />
            </ExpandableSettingsRow>
            <ExpandableSettingsRow icon={ShieldCheck} label="Accessibility" value="Motion and contrast" open={openPanel === "accessibility"} onToggle={() => togglePanel("accessibility")}>
              <div className="grid gap-2"><ToggleRow label="Reduced motion" checked={preferences.reducedMotion} onChange={(value) => updatePreference({ reducedMotion: value })} /><ToggleRow label="High contrast" checked={preferences.highContrast} onChange={(value) => updatePreference({ highContrast: value })} /></div>
            </ExpandableSettingsRow>
            <ExpandableSettingsRow icon={Languages} label="Language" value={preferences.language} open={openPanel === "language"} onToggle={() => togglePanel("language")}>
              <select className="input-base" value={preferences.language} onChange={(event) => updatePreference({ language: event.target.value })}><option value="en-US">English (US)</option><option value="en-GB">English (UK)</option><option value="fr-FR">French</option><option value="yo-NG">Yoruba</option></select>
            </ExpandableSettingsRow>
            {accessibilityStatus ? <p className="border-t border-border/60 px-4 py-3 text-xs font-semibold text-success sm:px-5">{accessibilityStatus}</p> : null}
          </SettingsGroup>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default RoleSettingsPage;
