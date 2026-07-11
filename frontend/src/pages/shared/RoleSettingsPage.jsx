import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Accessibility,
  CheckCircle2,
  ChevronRight,
  Database,
  Download,
  Eye,
  Mail,
  Moon,
  Save,
  ShieldCheck,
  Sun,
  UserRound,
} from "lucide-react";

import DashboardLayout from "../../components/layout/DashboardLayout";
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
    description: "Manage your admin account, accessibility preferences, profile, and data export.",
  },
  teacher: {
    title: "Settings",
    description: "Tune your workspace, keep your email current, and jump into your teacher profile.",
  },
  student: {
    title: "Settings",
    description: "Personalize your learning space without crowding your dashboard.",
  },
  parent: {
    title: "Settings",
    description: "Manage your parent account preferences, accessibility, and profile details.",
  },
};

const sectionItems = [
  { id: "email", label: "Email", icon: Mail },
  { id: "accessibility", label: "Accessibility", icon: Accessibility },
  { id: "profile", label: "Profile", icon: UserRound },
  { id: "data", label: "Data", icon: Database },
];

function resolveCurrentEmail(user) {
  return user?.email || user?.email_address || user?.account_email || "";
}

function SettingsSection({ id, icon: Icon, title, description, children }) {
  return (
    <section id={id} className="grid gap-3 lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-6">
      <div className="flex gap-3 lg:block">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary-soft text-primary">
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0 lg:mt-3">
          <h2 className="text-base font-semibold text-text sm:text-lg">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-text-muted">{description}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function ToggleRow({ label, description, checked, onChange }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 border-t border-border py-4 first:border-t-0 first:pt-0">
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-text">{label}</span>
        <span className="mt-0.5 block text-xs leading-5 text-text-muted">{description}</span>
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-5 w-5 shrink-0 accent-primary"
      />
    </label>
  );
}

function RoleSettingsPage({ role }) {
  const normalizedRole = String(role || "admin").toLowerCase();
  const user = authSession.getUser() || {};
  const copy = roleCopy[normalizedRole] || roleCopy.admin;
  const displayName = getUserDisplayName(user);
  const currentEmail = resolveCurrentEmail(user);
  const [emailForm, setEmailForm] = useState({
    newEmail: "",
    password: "",
  });
  const [emailStatus, setEmailStatus] = useState("");
  const [preferences, setPreferences] = useState(() => getSavedAccessibilityPreferences());
  const [accessibilityStatus, setAccessibilityStatus] = useState("");
  const [dataStatus, setDataStatus] = useState("");

  const profileSummary = [
    user?.role || normalizedRole,
    user?.class_name || user?.student_class || user?.specialization || user?.tenant?.name,
  ].filter(Boolean).join(" / ");

  const updatePreference = (patch) => {
    const nextPreferences = { ...preferences, ...patch };
    setPreferences(nextPreferences);
    applyAccessibilityPreferences(nextPreferences);
    saveAccessibilityPreferences(nextPreferences);
    setAccessibilityStatus("Accessibility preferences saved on this device.");
  };

  const handleEmailSubmit = (event) => {
    event.preventDefault();
    setEmailStatus("Email change request prepared. Backend verification can be attached here.");
    setEmailForm({ newEmail: "", password: "" });
  };

  const handleDownloadData = () => {
    const payload = {
      exported_at: new Date().toISOString(),
      role: normalizedRole,
      account: {
        name: displayName,
        email: currentEmail,
        profile_summary: profileSummary,
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
      <div className="mx-auto grid w-full max-w-6xl gap-5 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <Card className="p-2">
            <nav className="grid gap-1" aria-label="Settings sections">
              {sectionItems.map((item) => {
                const Icon = item.icon;
                return (
                  <a
                    key={item.id}
                    href={`#${item.id}`}
                    className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold text-text-soft transition hover:bg-surface-muted hover:text-text"
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </a>
                );
              })}
            </nav>
          </Card>
        </aside>

        <div className="space-y-6">
          <SettingsSection
            id="email"
            icon={Mail}
            title="Account email"
            description="Use this area for email changes and later verification."
          >
            <Card className="p-4 sm:p-6">
              <form onSubmit={handleEmailSubmit} className="grid gap-4">
                <div>
                  <label className="text-sm font-semibold text-text" htmlFor="current-email">Current email</label>
                  <input id="current-email" className="input-base mt-2" value={currentEmail || "No email on file"} readOnly />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="text-sm font-semibold text-text" htmlFor="new-email">New email</label>
                    <input
                      id="new-email"
                      type="email"
                      className="input-base mt-2"
                      placeholder="Enter new email"
                      value={emailForm.newEmail}
                      onChange={(event) => setEmailForm((current) => ({ ...current, newEmail: event.target.value }))}
                      required
                    />
                  </div>
                  <div>
                    <label className="text-sm font-semibold text-text" htmlFor="confirm-password">Confirm password</label>
                    <input
                      id="confirm-password"
                      type="password"
                      className="input-base mt-2"
                      placeholder="Current password"
                      value={emailForm.password}
                      onChange={(event) => setEmailForm((current) => ({ ...current, password: event.target.value }))}
                      required
                    />
                  </div>
                </div>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs leading-5 text-text-muted">For security, the backend should verify the password before changing email.</p>
                  <Button type="submit" className="sm:w-auto">
                    <Save className="h-4 w-4" />
                    Save changes
                  </Button>
                </div>
                {emailStatus ? <p className="rounded-xl bg-success-soft px-3 py-2 text-sm font-medium text-success">{emailStatus}</p> : null}
              </form>
            </Card>
          </SettingsSection>

          <SettingsSection
            id="accessibility"
            icon={Accessibility}
            title="Accessibility"
            description="These controls update the current browser immediately."
          >
            <Card className="p-4 sm:p-6">
              <div>
                <p className="text-sm font-semibold text-text">Theme mode</p>
                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  {[
                    { value: "light", label: "Light", icon: Sun },
                    { value: "dark", label: "Dark", icon: Moon },
                    { value: "system", label: "System", icon: Eye },
                  ].map((item) => {
                    const Icon = item.icon;
                    const active = preferences.theme === item.value;
                    return (
                      <button
                        key={item.value}
                        type="button"
                        onClick={() => updatePreference({ theme: item.value })}
                        className={cn(
                          "flex min-h-11 items-center justify-center gap-2 rounded-xl border px-3 text-sm font-semibold transition",
                          active ? "border-primary bg-primary-subtle text-primary" : "border-border bg-surface text-text-soft hover:bg-surface-muted",
                        )}
                      >
                        <Icon className="h-4 w-4" />
                        {item.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="mt-5 border-t border-border pt-5">
                <div className="flex items-center justify-between gap-4">
                  <label htmlFor="font-size" className="text-sm font-semibold text-text">Font size</label>
                  <span className="text-sm font-semibold text-text-muted">{preferences.fontScale}%</span>
                </div>
                <input
                  id="font-size"
                  className="mt-3 w-full accent-primary"
                  type="range"
                  min="90"
                  max="115"
                  step="5"
                  value={preferences.fontScale}
                  onChange={(event) => updatePreference({ fontScale: Number(event.target.value) })}
                />
              </div>

              <div className="mt-5">
                <ToggleRow
                  label="Reduced motion"
                  description="Minimize animated transitions where the app supports it."
                  checked={preferences.reducedMotion}
                  onChange={(value) => updatePreference({ reducedMotion: value })}
                />
                <ToggleRow
                  label="High contrast"
                  description="Strengthen borders and text contrast for readability."
                  checked={preferences.highContrast}
                  onChange={(value) => updatePreference({ highContrast: value })}
                />
              </div>

              <div className="border-t border-border pt-4">
                <label className="text-sm font-semibold text-text" htmlFor="language">Language</label>
                <select
                  id="language"
                  className="input-base mt-2"
                  value={preferences.language}
                  onChange={(event) => updatePreference({ language: event.target.value })}
                >
                  <option value="en-US">English (US)</option>
                  <option value="en-GB">English (UK)</option>
                  <option value="fr-FR">French</option>
                  <option value="yo-NG">Yoruba</option>
                </select>
              </div>
              {accessibilityStatus ? <p className="mt-4 rounded-xl bg-success-soft px-3 py-2 text-sm font-medium text-success">{accessibilityStatus}</p> : null}
            </Card>
          </SettingsSection>

          <SettingsSection
            id="profile"
            icon={UserRound}
            title="Profile"
            description="Open the full profile view and passport photo manager."
          >
            <Card className="p-4 sm:p-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-text">{displayName || "Your profile"}</p>
                  <p className="mt-1 text-sm text-text-muted">{profileSummary || "Profile details and passport photo"}</p>
                </div>
                <Link to="/profile" className="shrink-0">
                  <Button variant="outline" className="w-full sm:w-auto">
                    View profile
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </Link>
              </div>
            </Card>
          </SettingsSection>

          <SettingsSection
            id="data"
            icon={Database}
            title="Data and backup"
            description="Download a local copy of current account settings while backend export is pending."
          >
            <Card className="p-4 sm:p-6">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-text">Download my data</p>
                  <p className="mt-1 text-sm leading-6 text-text-muted">Exports your visible account summary and accessibility preferences as JSON.</p>
                </div>
                <Button type="button" variant="outline" className="shrink-0" onClick={handleDownloadData}>
                  <Download className="h-4 w-4" />
                  Download my data
                </Button>
              </div>
              {dataStatus ? (
                <p className="mt-4 flex items-center gap-2 rounded-xl bg-success-soft px-3 py-2 text-sm font-medium text-success">
                  <CheckCircle2 className="h-4 w-4" />
                  {dataStatus}
                </p>
              ) : null}
              <div className="mt-4 flex items-start gap-2 rounded-xl border border-border bg-surface-muted/35 px-3 py-3 text-xs leading-5 text-text-muted">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                Backend backup should later include audit logs, academic records, uploaded media metadata, and verified email history.
              </div>
            </Card>
          </SettingsSection>
        </div>
      </div>
    </DashboardLayout>
  );
}

export default RoleSettingsPage;
