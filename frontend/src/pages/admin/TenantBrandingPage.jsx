import { ExternalLink, Monitor, Moon, Palette, Save, Sun } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import ConfirmDialog from "../../components/shared/ConfirmDialog";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Input from "../../components/ui/Input";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { useTenantBranding } from "../../features/tenant-branding/useTenantBranding";
import { useToast } from "../../hooks/useToast";
import { getErrorMessage } from "../../services/api";
import { tenantBrandingService } from "../../services/tenantBrandingService";

const DEFAULT_FORM = {
  brand_name: "Weave", primary_color: "#1D4ED8", accent_color: "#4F46E5",
  sidebar_color: "#FFFFFF", header_color: "#FFFFFF",
  background_color: "#F8FAFC", surface_color: "#FFFFFF",
};
const COLOR_FIELDS = [
  ["primary_color", "Primary colour"], ["accent_color", "Accent colour"],
  ["sidebar_color", "Sidebar colour"], ["header_color", "Header colour"],
  ["background_color", "Workspace background"], ["surface_color", "Card colour"],
];
const HEX = /^#[0-9A-Fa-f]{6}$/;

function readableText(hex) {
  if (!HEX.test(hex)) return "#0F172A";
  const [r, g, b] = [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16));
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) > 150 ? "#0F172A" : "#FFFFFF";
}

function toEffective(response) {
  return {
    ...response,
    is_default_theme: !response?.is_enabled,
  };
}

function BrandingPreview({ form, dark = false, mobile = false }) {
  const background = dark ? "#0A0F1C" : form.background_color;
  const surface = dark ? "#0F172A" : form.surface_color;
  const text = dark ? "#F8FAFC" : "#0F172A";
  const muted = dark ? "#94A3B8" : "#64748B";
  const sidebar = dark ? "#0F172A" : form.sidebar_color;
  const header = dark ? "#0F172A" : form.header_color;
  return (
    <div className={`overflow-hidden rounded-2xl border shadow-sm ${mobile ? "mx-auto max-w-[20rem]" : ""}`} style={{ background, color: text }}>
      <div className="flex min-h-[18rem]">
        <aside className={`${mobile ? "w-14" : "w-28"} border-r p-2`} style={{ background: sidebar, color: readableText(sidebar), borderColor: `${muted}40` }}>
          <div className="mb-4 h-7 w-7 rounded-lg" style={{ background: form.primary_color }} />
          {[0, 1, 2].map((item) => <div key={item} className="mb-2 h-7 rounded-lg opacity-70" style={{ background: item === 0 ? form.primary_color : `${readableText(sidebar)}18` }} />)}
        </aside>
        <div className="min-w-0 flex-1">
          <header className="flex h-12 items-center justify-between border-b px-3" style={{ background: header, color: readableText(header), borderColor: `${muted}40` }}><span className="truncate text-xs font-bold">{form.brand_name || "School"}</span><span className="h-7 w-7 rounded-full" style={{ background: `${readableText(header)}18` }} /></header>
          <main className="space-y-3 p-3">
            <div className="flex gap-2"><button className="rounded-lg px-3 py-2 text-xs font-bold" style={{ background: form.primary_color, color: readableText(form.primary_color) }}>Primary</button><button className="rounded-lg border px-3 py-2 text-xs font-bold" style={{ borderColor: form.accent_color, color: form.accent_color }}>Secondary</button></div>
            <div className="rounded-xl border p-3" style={{ background: surface, borderColor: `${muted}40` }}><div className="mb-2 flex items-center justify-between"><strong className="text-xs">Attendance</strong><span className="rounded-full px-2 py-1 text-[10px]" style={{ background: `${form.accent_color}25`, color: form.accent_color }}>Active</span></div><div className="h-9 rounded-lg border px-2 py-2 text-[10px]" style={{ borderColor: `${muted}60`, color: muted }}>Search students</div><div className="mt-2 rounded-lg px-2 py-2 text-[10px]" style={{ background: `${form.primary_color}16` }}>Selected table row</div></div>
          </main>
        </div>
      </div>
    </div>
  );
}

export default function TenantBrandingPage() {
  const { planCode } = useSubscription();
  const { applyResponse, logoUrl, schoolName } = useTenantBranding();
  const { showError, showSuccess } = useToast();
  const [form, setForm] = useState({ ...DEFAULT_FORM, brand_name: schoolName || "Weave" });
  const [baseline, setBaseline] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [resetOpen, setResetOpen] = useState(false);
  const eligible = ["professional", "enterprise"].includes(String(planCode || "").toLowerCase());
  const dirty = baseline !== null && JSON.stringify(form) !== JSON.stringify(baseline);
  const valid = form.brand_name.trim() && COLOR_FIELDS.every(([field]) => HEX.test(form[field]));

  useEffect(() => {
    if (!eligible) { setLoading(false); return; }
    tenantBrandingService.getAdmin().then((response) => {
      const next = Object.fromEntries(Object.keys(DEFAULT_FORM).map((key) => [key, response[key] || DEFAULT_FORM[key]]));
      setForm(next); setBaseline(next); setEnabled(Boolean(response.is_enabled));
    }).catch((error) => showError(getErrorMessage(error, "Could not load school branding."))).finally(() => setLoading(false));
  }, [eligible, showError]);

  useEffect(() => {
    const beforeUnload = (event) => { if (!dirty) return; event.preventDefault(); event.returnValue = ""; };
    const protectLinks = (event) => {
      if (!dirty) return;
      const anchor = event.target.closest?.("a[href]");
      if (anchor && !window.confirm("Discard your unsaved branding changes?")) event.preventDefault();
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", protectLinks, true);
    return () => { window.removeEventListener("beforeunload", beforeUnload); document.removeEventListener("click", protectLinks, true); };
  }, [dirty]);

  const errors = useMemo(() => Object.fromEntries(COLOR_FIELDS.map(([field]) => [field, HEX.test(form[field]) ? "" : "Use full hexadecimal format, for example #1D4ED8."])), [form]);
  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  const persist = async (mode) => {
    if (!valid) return;
    setBusy(mode);
    try {
      let response;
      if (mode === "disable") response = await tenantBrandingService.disable();
      else response = await tenantBrandingService.update({ ...form, ...(mode === "enable" ? { is_enabled: true } : {}) });
      const nextEnabled = mode === "disable" ? false : Boolean(response.is_enabled);
      setEnabled(nextEnabled);
      if (mode !== "disable") setBaseline(form);
      applyResponse(toEffective(response));
      showSuccess(mode === "save" ? "Branding draft saved." : mode === "enable" ? "School branding enabled." : "School branding disabled.");
    } catch (error) { showError(getErrorMessage(error, "Could not update school branding.")); }
    finally { setBusy(""); }
  };

  const restoreDefaults = async () => {
    setBusy("reset");
    try {
      const response = await tenantBrandingService.reset();
      const next = { ...DEFAULT_FORM, brand_name: response.brand_name || schoolName || "Weave" };
      setForm(next); setBaseline(next); setEnabled(false); applyResponse(response);
      setResetOpen(false); showSuccess("Weave defaults restored. Your school logo was kept.");
    } catch (error) { showError(getErrorMessage(error, "Could not restore Weave defaults.")); }
    finally { setBusy(""); }
  };

  if (!eligible) return <Card className="mx-auto max-w-2xl p-6"><Palette className="h-8 w-8 text-primary" /><h1 className="mt-4 text-xl font-bold">School branding</h1><p className="mt-2 text-text-muted">School branding is available on Professional and Enterprise plans.</p><Link to="/admin/billing/plans" className="mt-5 inline-flex font-semibold text-primary">View plans</Link></Card>;
  if (loading) return <Card className="mx-auto max-w-2xl p-6 text-text-muted">Loading school branding…</Card>;

  return (
    <div className="mx-auto w-full max-w-7xl space-y-5 pb-24">
      <div><h1 className="text-2xl font-bold">School branding</h1><p className="mt-1 text-sm text-text-muted">A controlled palette shared by every user in this school. Appearance mode remains each user’s choice.</p></div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.8fr)_minmax(32rem,1.2fr)]">
        <div className="space-y-5">
          <Card className="space-y-4"><h2 className="font-bold">School identity</h2><div className="flex items-center gap-4">{logoUrl ? <img src={logoUrl} alt="Current school logo" className="h-16 w-16 rounded-xl border bg-surface object-contain p-1" /> : <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-surface-muted text-xs text-text-muted">No logo</div>}<div><p className="text-sm text-text-muted">The logo continues to use Weave’s secure media upload.</p><Link to="/profile" className="mt-1 inline-flex items-center gap-1 text-sm font-bold text-primary">Manage school logo <ExternalLink className="h-3.5 w-3.5" /></Link></div></div><Input label="Brand name" value={form.brand_name} onChange={(event) => update("brand_name", event.target.value)} maxLength={255} /></Card>
          <Card><h2 className="font-bold">Brand palette</h2><div className="mt-4 grid gap-4 sm:grid-cols-2">{COLOR_FIELDS.map(([field, label]) => <div key={field}><label className="mb-1.5 block text-sm font-medium text-text-soft">{label}</label><div className="flex gap-2"><input type="color" value={HEX.test(form[field]) ? form[field] : "#000000"} onChange={(event) => update(field, event.target.value.toUpperCase())} className="h-11 w-12 rounded-lg border bg-surface p-1" aria-label={`${label} picker`} /><Input value={form[field]} onChange={(event) => update(field, event.target.value.toUpperCase())} error={errors[field]} maxLength={7} /></div></div>)}</div></Card>
        </div>
        <Card><div className="flex items-center justify-between"><div><h2 className="font-bold">Live preview</h2><p className="text-sm text-text-muted">Unsaved values stay isolated here.</p></div><Monitor className="h-5 w-5 text-text-muted" /></div><div className="mt-4 grid gap-4 lg:grid-cols-2"><div><p className="mb-2 flex items-center gap-2 text-xs font-bold text-text-muted"><Sun className="h-4 w-4" /> Light desktop</p><BrandingPreview form={form} /></div><div><p className="mb-2 flex items-center gap-2 text-xs font-bold text-text-muted"><Moon className="h-4 w-4" /> Dark mobile</p><BrandingPreview form={form} dark mobile /></div></div></Card>
      </div>
      <div className="sticky bottom-3 z-20 flex flex-wrap items-center gap-2 rounded-2xl border bg-surface/95 p-3 shadow-premium backdrop-blur"><span className={`mr-auto text-sm font-semibold ${enabled ? "text-success" : "text-text-muted"}`}>{enabled ? "Branding enabled" : "Branding disabled"}{dirty ? " · Unsaved changes" : ""}</span><Button variant="outline" onClick={() => setResetOpen(true)} disabled={Boolean(busy)}>Restore Weave defaults</Button>{enabled ? <Button variant="outline" onClick={() => persist("disable")} disabled={Boolean(busy)}>Disable branding</Button> : null}<Button variant="outline" onClick={() => persist("save")} disabled={Boolean(busy) || !valid}><Save className="h-4 w-4" />Save draft</Button><Button onClick={() => persist("enable")} disabled={Boolean(busy) || !valid}>Enable branding</Button></div>
      <ConfirmDialog open={resetOpen} title="Restore Weave defaults?" description="This will remove the school’s custom colour palette for every user. The school logo and school profile will not be deleted." cancelLabel="Cancel" confirmLabel="Restore defaults" variant="danger" isLoading={busy === "reset"} onCancel={() => setResetOpen(false)} onConfirm={restoreDefaults} />
    </div>
  );
}
