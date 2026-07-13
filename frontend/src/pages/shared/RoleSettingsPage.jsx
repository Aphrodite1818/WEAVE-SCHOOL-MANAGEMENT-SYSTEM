import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Accessibility,
  CheckCircle2,
  ChevronRight,
  ChevronDown,
  Database,
  Download,
  Eye,
  IdCard,
  Languages,
  Mail,
  Moon,
  Save,
  ShieldCheck,
  Sun,
  UserRound,
} from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
import Avatar from "../../components/ui/Avatar";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import { authSession } from "../../services/api";
import {
  applyAccessibilityPreferences,
  getSavedAccessibilityPreferences,
  saveAccessibilityPreferences,
} from "../../utils/accessibilityPreferences";
import { cn } from "../../utils/cn";
import { getUserDisplayName } from "../../utils/user";

const roleCopy = {
  admin: {
    title: "Settings",
    description: "Manage account access, profile details, accessibility, and data export.",
  },
  teacher: {
    title: "Settings",
    description: "Keep your teacher workspace compact, readable, and current.",
  },
  student: {
    title: "Settings",
    description: "Manage your workspace preferences.",
  },
  parent: {
    title: "Settings",
    description: "Manage parent account preferences, profile details, and data.",
  },
};

const themeOptions = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Eye },
];

function resolveCurrentEmail(user) {
  return user?.email || user?.email_address || user?.account_email || "";
}

function resolveAdmissionNumber(user) {
  return user?.admission_number || user?.student?.admission_number || user?.profile?.admission_number || "";
}

function SettingsGroup({ title, children }) {
  return (
    <section className="space-y-2">
      <h2 className="px-1 text-xs font-bold uppercase tracking-wide text-text-muted sm:text-sm">
        {title}
      </h2>
      <Card className="overflow-hidden rounded-[1.35rem] border-border/80 p-0 shadow-sm">
        {children}
      </Card>
    </section>
  );
}

function SettingsRow({ icon: Icon, label, value, children, to, accent = false }) {
  const content = (
    <div className="flex min-h-[3.35rem] items-center gap-3 border-t border-border/70 px-4 py-3 first:border-t-0 sm:min-h-[3.75rem] sm:px-5">
      <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-muted text-text-soft", accent && "bg-primary-soft text-primary")}>
        <Icon className="h-[18px] w-[18px]" />
      </span>
      <div className="min-w-0 flex-1">
        <p className={cn("truncate text-sm font-semibold text-text sm:text-base", accent && "text-primary")}>{label}</p>
        {children ? <div className="mt-2">{children}</div> : null}
      </div>
      {value ? <p className="max-w-[48%] truncate text-right text-sm text-text-muted">{value}</p> : null}
      {to ? <ChevronRight className="h-4 w-4 shrink-0 text-text-faint" /> : null}
    </div>
  );

  return to ? (
    <Link to={to} className="block transition hover:bg-surface-muted/45">
      {content}
    </Link>
  ) : (
    content
  );
}

function ExpandableSettingsRow({ icon: Icon, label, value, open, onToggle, children }) {
  return (
    <div className="border-t border-border/70 first:border-t-0">
      <button
        type="button"
        onClick={onToggle}
        className="flex min-h-[3.35rem] w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-surface-muted/45 sm:min-h-[3.75rem] sm:px-5"
        aria-expanded={open}
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-muted text-text-soft">
          <Icon className="h-[18px] w-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-text sm:text-base">{label}</p>
          {value ? <p className="mt-0.5 truncate text-xs text-text-muted">{value}</p> : null}
        </div>
        {open ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-text-faint" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-text-faint" />
        )}
      </button>
      {open ? <div className="border-t border-border/60 px-4 py-4 sm:px-5">{children}</div> : null}
    </div>
  );
}

function ToggleRow({ label, checked, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="flex w-full items-center justify-between rounded-xl py-1 text-left"
    >
      <span className="text-sm font-medium text-text-soft">{label}</span>
      <span className={cn("relative h-6 w-11 rounded-full transition", checked ? "bg-primary" : "bg-border")}>
        <span className={cn("absolute top-1 h-4 w-4 rounded-full bg-white shadow-sm transition", checked ? "left-6" : "left-1")} />
      </span>
    </button>
  );
}

function RoleSettingsPage({ role }) {
  const normalizedRole = String(role || "admin").toLowerCase();
  const user = authSession.getUser() || {};
  const copy = roleCopy[normalizedRole] || roleCopy.admin;
  const isStudent = normalizedRole === "student";
  const displayName = getUserDisplayName(user);
  const currentEmail = resolveCurrentEmail(user);
  const admissionNumber = resolveAdmissionNumber(user);
  const [emailForm, setEmailForm] = useState({ newEmail: "", password: "" });
  const [emailStatus, setEmailStatus] = useState("");
  const [preferences, setPreferences] = useState(() => getSavedAccessibilityPreferences());
  const [accessibilityStatus, setAccessibilityStatus] = useState("");
  const [dataStatus, setDataStatus] = useState("");
  const [openPanel, setOpenPanel] = useState("");

  const profileSummary = [
    user?.role || normalizedRole,
    user?.class_name || user?.student_class || user?.specialization || user?.tenant?.name,
  ].filter(Boolean).join(" / ");

  const updatePreference = (patch) => {
    const nextPreferences = { ...preferences, ...patch };
    setPreferences(nextPreferences);
    applyAccessibilityPreferences(nextPreferences);
    saveAccessibilityPreferences(nextPreferences);
    setAccessibilityStatus("Preferences saved on this device.");
  };

  const togglePanel = (panel) => {
    setOpenPanel((current) => (current === panel ? "" : panel));
  };

  const handleEmailSubmit = (event) => {
    event.preventDefault();
    setEmailStatus("Email change request prepared.");
    setEmailForm({ newEmail: "", password: "" });
  };

  const handleDownloadData = () => {
    const payload = {
      exported_at: new Date().toISOString(),
      role: normalizedRole,
      account: {
        name: displayName,
        profile_summary: profileSummary,
        ...(isStudent ? { admission_number: admissionNumber } : { email: currentEmail }),
      },
      accessibility: preferences,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${normalizedRole}-account-data.json`;
    link.click();
    URL.revokeObjectURL(url);
    setDataStatus("Your account data file has been generated.");
  };

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
              <Link to="/profile" className="flex items-center justify-between rounded-2xl px-3 py-3 text-sm font-semibold text-text-soft transition hover:bg-surface-muted hover:text-text">
                Profile details
                <ChevronRight className="h-4 w-4" />
              </Link>
              <a href="#account" className="flex items-center justify-between rounded-2xl px-3 py-3 text-sm font-semibold text-text-soft transition hover:bg-surface-muted hover:text-text">
                Account
                <ChevronRight className="h-4 w-4" />
              </a>
            </div>
          </Card>
        </aside>

        <div className="space-y-5 pb-24 md:pb-0">
          <SettingsGroup title="Account">
            {isStudent ? (
              <SettingsRow icon={IdCard} label="Admission number" value={admissionNumber || "Not assigned"} />
            ) : (
              <SettingsRow icon={Mail} label="Email" value={currentEmail || "No email on file"} />
            )}
            <SettingsRow icon={UserRound} label="Profile" value={profileSummary || "Details and photo"} to="/profile" />
            {!isStudent ? (
              <ExpandableSettingsRow
                icon={Mail}
                label="Change email"
                value="Requires password verification"
                open={openPanel === "email"}
                onToggle={() => togglePanel("email")}
              >
                <form onSubmit={handleEmailSubmit} className="grid gap-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input className="input-base" type="email" placeholder="New email" value={emailForm.newEmail} onChange={(event) => setEmailForm((current) => ({ ...current, newEmail: event.target.value }))} required />
                    <input className="input-base" type="password" placeholder="Current password" value={emailForm.password} onChange={(event) => setEmailForm((current) => ({ ...current, password: event.target.value }))} required />
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-xs leading-5 text-text-muted">Password verification is required before email changes are saved.</p>
                    <Button type="submit" className="min-h-10 sm:w-auto">
                      <Save className="h-4 w-4" />
                      Save
                    </Button>
                  </div>
                  {emailStatus ? <p className="rounded-xl bg-success-soft px-3 py-2 text-sm font-medium text-success">{emailStatus}</p> : null}
                </form>
              </ExpandableSettingsRow>
            ) : null}
            <ExpandableSettingsRow
              icon={Database}
              label="Download my data"
              value="Export account settings"
              open={openPanel === "data"}
              onToggle={() => togglePanel("data")}
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-5 text-text-muted">Export visible account settings as JSON.</p>
                <Button type="button" variant="outline" className="min-h-10 w-full sm:w-auto" onClick={handleDownloadData}>
                  <Download className="h-4 w-4" />
                  Download
                </Button>
              </div>
              {dataStatus ? <p className="mt-2 flex items-center gap-2 text-xs font-semibold text-success"><CheckCircle2 className="h-4 w-4" />{dataStatus}</p> : null}
            </ExpandableSettingsRow>
          </SettingsGroup>

          <SettingsGroup title="Theme">
            <ExpandableSettingsRow
              icon={Accessibility}
              label="Appearance"
              value={preferences.theme === "system" ? "System device preference" : preferences.theme}
              open={openPanel === "appearance"}
              onToggle={() => togglePanel("appearance")}
            >
              <div className="grid grid-cols-3 gap-2">
                {themeOptions.map((item) => {
                  const Icon = item.icon;
                  const active = preferences.theme === item.value;
                  return (
                    <button
                      key={item.value}
                      type="button"
                      onClick={() => updatePreference({ theme: item.value })}
                      className={cn(
                        "flex min-h-10 items-center justify-center gap-1.5 rounded-xl border px-2 text-xs font-bold transition sm:text-sm",
                        active ? "border-primary bg-primary-subtle text-primary" : "border-border bg-surface text-text-soft hover:bg-surface-muted"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </ExpandableSettingsRow>
            <ExpandableSettingsRow
              icon={Eye}
              label="Font size"
              value={`${preferences.fontScale}%`}
              open={openPanel === "font"}
              onToggle={() => togglePanel("font")}
            >
              <input className="w-full accent-primary" type="range" min="90" max="115" step="5" value={preferences.fontScale} onChange={(event) => updatePreference({ fontScale: Number(event.target.value) })} />
            </ExpandableSettingsRow>
            <ExpandableSettingsRow
              icon={ShieldCheck}
              label="Accessibility"
              value="Motion and contrast"
              open={openPanel === "accessibility"}
              onToggle={() => togglePanel("accessibility")}
            >
              <div className="grid gap-2">
                <ToggleRow label="Reduced motion" checked={preferences.reducedMotion} onChange={(value) => updatePreference({ reducedMotion: value })} />
                <ToggleRow label="High contrast" checked={preferences.highContrast} onChange={(value) => updatePreference({ highContrast: value })} />
              </div>
            </ExpandableSettingsRow>
            <ExpandableSettingsRow
              icon={Languages}
              label="Language"
              value={preferences.language}
              open={openPanel === "language"}
              onToggle={() => togglePanel("language")}
            >
              <select className="input-base" value={preferences.language} onChange={(event) => updatePreference({ language: event.target.value })}>
                <option value="en-US">English (US)</option>
                <option value="en-GB">English (UK)</option>
                <option value="fr-FR">French</option>
                <option value="yo-NG">Yoruba</option>
              </select>
              {accessibilityStatus ? <p className="mt-2 text-xs font-semibold text-success">{accessibilityStatus}</p> : null}
            </ExpandableSettingsRow>
          </SettingsGroup>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default RoleSettingsPage;
