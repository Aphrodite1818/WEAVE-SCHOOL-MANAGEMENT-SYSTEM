import { Check, ExternalLink, Moon, Palette, Save, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import ConfirmDialog from "../../components/shared/ConfirmDialog";
import Button from "../../components/ui/Button";
import Card from "../../components/ui/Card";
import Modal from "../../components/ui/Modal";
import { useSubscription } from "../../features/subscriptions/useSubscription";
import { useTenantBranding } from "../../features/tenant-branding/useTenantBranding";
import { useToast } from "../../hooks/useToast";
import { getErrorMessage } from "../../services/api";
import { tenantBrandingService } from "../../services/tenantBrandingService";

const DEFAULT_PALETTE = "blue";
const PALETTES = [
  { key: "blue", name: "Classic blue", description: "Clear and familiar", primary: "#1D4ED8", accent: "#4F46E5", dark: "#172554", tint: "#EFF6FF", darkTint: "#111C35" },
  { key: "royal_gold", name: "Royal and gold", description: "A common school crest pairing", primary: "#1D4ED8", accent: "#D97706", dark: "#172554", tint: "#EFF6FF", darkTint: "#111C35" },
  { key: "navy", name: "Deep navy", description: "Formal and trusted", primary: "#1E3A8A", accent: "#3B82F6", dark: "#111D3F", tint: "#EFF6FF", darkTint: "#10182A" },
  { key: "navy_gold", name: "Navy and gold", description: "Traditional and prestigious", primary: "#1E3A8A", accent: "#D97706", dark: "#111D3F", tint: "#EFF6FF", darkTint: "#10182A" },
  { key: "indigo_gold", name: "Indigo and gold", description: "Polished and ceremonial", primary: "#3730A3", accent: "#F59E0B", dark: "#1E1B4B", tint: "#EEF2FF", darkTint: "#171A31" },
  { key: "gold", name: "Warm gold", description: "Welcoming and confident", primary: "#A16207", accent: "#D97706", dark: "#3B2305", tint: "#FFFBEB", darkTint: "#1C160B" },
  { key: "black_gold", name: "Black and gold", description: "Strong house-style identity", primary: "#111827", accent: "#D97706", dark: "#030712", tint: "#F9FAFB", darkTint: "#111827" },
  { key: "orange", name: "Burnt orange", description: "Bold and optimistic", primary: "#C2410C", accent: "#F97316", dark: "#431407", tint: "#FFF7ED", darkTint: "#28150D" },
  { key: "emerald", name: "Emerald", description: "Calm and established", primary: "#047857", accent: "#10B981", dark: "#052E2B", tint: "#ECFDF5", darkTint: "#0B2422" },
  { key: "green_gold", name: "Green and gold", description: "Classic academic colours", primary: "#166534", accent: "#D97706", dark: "#0D2F1C", tint: "#F0FDF4", darkTint: "#102419" },
  { key: "forest", name: "Forest", description: "Grounded and academic", primary: "#166534", accent: "#22C55E", dark: "#0D2F1C", tint: "#F0FDF4", darkTint: "#102419" },
  { key: "teal_gold", name: "Teal and gold", description: "Fresh with a formal accent", primary: "#0F766E", accent: "#D97706", dark: "#042F2E", tint: "#F0FDFA", darkTint: "#0B2423" },
  { key: "violet", name: "Violet", description: "Modern and expressive", primary: "#7C3AED", accent: "#8B5CF6", dark: "#2E1065", tint: "#F5F3FF", darkTint: "#1D1633" },
  { key: "purple_gold", name: "Purple and gold", description: "Ceremonial and distinctive", primary: "#6D28D9", accent: "#D97706", dark: "#2E1065", tint: "#F5F3FF", darkTint: "#1D1633" },
  { key: "plum", name: "Plum", description: "Distinctive and refined", primary: "#86198F", accent: "#D946EF", dark: "#3B0A40", tint: "#FDF4FF", darkTint: "#251127" },
  { key: "burgundy_cream", name: "Burgundy and cream", description: "Warm and established", primary: "#881337", accent: "#F59E0B", dark: "#4C0519", tint: "#FFF1F2", darkTint: "#2B1119" },
  { key: "maroon_gold", name: "Maroon and gold", description: "Traditional school colours", primary: "#7F1D1D", accent: "#D97706", dark: "#450A0A", tint: "#FEF2F2", darkTint: "#241111" },
  { key: "rose", name: "Rose", description: "Warm and energetic", primary: "#BE123C", accent: "#E11D48", dark: "#4C0519", tint: "#FFF1F2", darkTint: "#2B1119" },
  { key: "crimson_gray", name: "Crimson and gray", description: "Assertive and disciplined", primary: "#B91C1C", accent: "#64748B", dark: "#450A0A", tint: "#FEF2F2", darkTint: "#241111" },
  { key: "red_navy", name: "Red and navy", description: "Sporting and confident", primary: "#B91C1C", accent: "#1D4ED8", dark: "#450A0A", tint: "#FEF2F2", darkTint: "#241111" },
  { key: "teal", name: "Teal", description: "Balanced and dependable", primary: "#0F766E", accent: "#14B8A6", dark: "#042F2E", tint: "#F0FDFA", darkTint: "#0B2423" },
  { key: "cyan", name: "Ocean cyan", description: "Fresh and focused", primary: "#0E7490", accent: "#06B6D4", dark: "#083344", tint: "#ECFEFF", darkTint: "#0B2229" },
  { key: "sky_navy", name: "Sky and navy", description: "Bright but still formal", primary: "#0369A1", accent: "#1E3A8A", dark: "#082F49", tint: "#F0F9FF", darkTint: "#0B2231" },
  { key: "slate", name: "Slate", description: "Quiet and professional", primary: "#334155", accent: "#64748B", dark: "#172033", tint: "#F1F5F9", darkTint: "#151B26" },
  { key: "charcoal_red", name: "Charcoal and red", description: "Structured and energetic", primary: "#374151", accent: "#DC2626", dark: "#111827", tint: "#F9FAFB", darkTint: "#151B26" },
];

function toEffective(response) {
  return { ...response, is_default_theme: !response?.is_enabled };
}

function ThemePreview({ palette, dark = false }) {
  const background = dark ? "#0F172A" : "#F7F4EE";
  const foreground = dark ? "#F8FAFC" : "#0F172A";
  const muted = dark ? "#94A3B8" : "#64748B";
  const chrome = dark ? "#0F172A" : palette.primary;
  const card = dark ? "#111827" : palette.tint;
  const header = dark ? "#0F172A" : "#FFFFFF";
  const headerText = dark ? "#F8FAFC" : "#0F172A";

  return (
    <div className="overflow-hidden rounded-xl border border-border" style={{ background, color: foreground }}>
      <header className="flex h-10 items-center justify-between border-b px-3 text-xs font-bold" style={{ background: header, color: headerText, borderColor: `${muted}30` }}>
        <span>School workspace</span><span className="h-6 w-6 rounded-full bg-white/20" />
      </header>
      <div className="flex min-h-44">
        <aside className="w-16 space-y-2 p-2" style={{ background: chrome }}>
          {[1, 2, 3].map((item) => <div key={item} className="h-7 rounded-md" style={{ background: item === 1 ? palette.primary : dark ? "rgb(255 255 255 / 0.08)" : "rgb(0 0 0 / 0.10)" }} />)}
        </aside>
        <main className="min-w-0 flex-1 space-y-2 p-3">
          <div className="relative overflow-hidden rounded-lg border px-3 py-3 text-xs font-bold text-white" style={{ background: dark ? "#182236" : palette.primary, borderColor: dark ? "#263247" : palette.primary }}><span className="absolute inset-x-0 top-0 h-1" style={{ background: palette.primary }} />Welcome back</div>
          <div className="rounded-lg border p-3" style={{ background: card, borderColor: `${muted}35` }}>
            <div className="h-2.5 w-20 rounded" style={{ background: palette.primary }} />
            <div className="mt-2 h-2 w-full rounded opacity-30" style={{ background: muted }} />
          </div>
        </main>
      </div>
    </div>
  );
}

export default function TenantBrandingPage() {
  const { planCode } = useSubscription();
  const { applyResponse, logoUrl, schoolName } = useTenantBranding();
  const { showError, showSuccess } = useToast();
  const [paletteKey, setPaletteKey] = useState(DEFAULT_PALETTE);
  const [baseline, setBaseline] = useState(null);
  const [identityName, setIdentityName] = useState(schoolName || "School");
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [resetOpen, setResetOpen] = useState(false);
  const [pendingPaletteKey, setPendingPaletteKey] = useState(null);
  const [previewMode, setPreviewMode] = useState("light");
  const eligible = ["professional", "enterprise"].includes(String(planCode || "").toLowerCase());
  const dirty = baseline !== null && paletteKey !== baseline;
  const selected = PALETTES.find((palette) => palette.key === paletteKey) || PALETTES[0];
  const pendingPalette = PALETTES.find((palette) => palette.key === pendingPaletteKey);

  useEffect(() => {
    if (!eligible) { setLoading(false); return; }
    tenantBrandingService.getAdmin().then((response) => {
      const next = response.palette_key || DEFAULT_PALETTE;
      setPaletteKey(next);
      setBaseline(next);
      setIdentityName(response.school_name || schoolName || "School");
      setEnabled(Boolean(response.is_enabled));
    }).catch((error) => showError(getErrorMessage(error, "Could not load school branding."))).finally(() => setLoading(false));
  }, [eligible, schoolName, showError]);

  useEffect(() => {
    const beforeUnload = (event) => { if (!dirty) return; event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  const persist = async (mode, nextPaletteKey = paletteKey) => {
    setBusy(mode);
    try {
      const response = mode === "disable"
        ? await tenantBrandingService.disable()
        : await tenantBrandingService.update({ palette_key: nextPaletteKey, ...(mode === "enable" ? { is_enabled: true } : {}) });
      setEnabled(Boolean(response.is_enabled));
      if (mode !== "disable") {
        setPaletteKey(nextPaletteKey);
        setBaseline(nextPaletteKey);
        setPendingPaletteKey(null);
      }
      applyResponse(toEffective(response));
      showSuccess(mode === "enable" ? "Colour theme is now live for your school." : mode === "disable" ? "School colour theme turned off." : enabled ? "Live colour theme updated." : "Colour choice saved. Turn it on when you are ready.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not update school branding."));
    } finally { setBusy(""); }
  };

  const restoreDefaults = async () => {
    setBusy("reset");
    try {
      const response = await tenantBrandingService.reset();
      setPaletteKey(DEFAULT_PALETTE);
      setBaseline(DEFAULT_PALETTE);
      setEnabled(false);
      applyResponse(response);
      setResetOpen(false);
      showSuccess("Weave colours restored. Your school name and logo were kept.");
    } catch (error) {
      showError(getErrorMessage(error, "Could not restore Weave colours."));
    } finally { setBusy(""); }
  };

  const closePaletteDialog = () => {
    if (busy) return;
    setPendingPaletteKey(null);
  };

  if (!eligible) return <Card className="mx-auto max-w-2xl p-6"><Palette className="h-8 w-8 text-primary" /><h1 className="mt-4 text-xl font-bold">School colours</h1><p className="mt-2 text-text-muted">School colours are available on Professional and Enterprise plans.</p><Link to="/admin/billing/plans" className="mt-5 inline-flex font-semibold text-primary">View plans</Link></Card>;
  if (loading) return <Card className="mx-auto max-w-2xl p-6 text-text-muted">Loading school colours…</Card>;

  return (
    <div className="mx-auto w-full max-w-6xl pb-10">
      <Card className="overflow-hidden border-border/60 p-0 shadow-sm">
        <div className="border-b border-border/60 px-5 py-6 sm:px-7">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-2xl"><h1 className="text-2xl font-bold tracking-tight text-text">School colour theme</h1><p className="mt-2 text-sm leading-6 text-text-muted">Choose one coordinated palette for navigation, actions and key highlights. Light and dark appearance remain each user’s choice.</p></div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <div className={`inline-flex w-fit items-center gap-2 rounded-full border px-3 py-2 text-xs font-bold ${enabled ? "border-success/25 bg-success/10 text-success" : "border-border bg-surface/80 text-text-muted"}`}><span className={`h-2 w-2 rounded-full ${enabled ? "bg-success" : "bg-text-faint"}`} />{enabled ? "Live across your school" : "Not currently live"}</div>
              <Button variant="ghost" onClick={() => setResetOpen(true)} disabled={Boolean(busy)}>Restore defaults</Button>
              {enabled ? <Button variant="outline" onClick={() => persist("disable")} disabled={Boolean(busy)}>Turn off</Button> : null}
            </div>
          </div>

          <div className="mt-5 flex flex-col gap-3 border-t border-border/60 pt-5 sm:flex-row sm:items-center">
            {logoUrl ? <img src={logoUrl} alt="Current school logo" className="h-11 w-11 rounded-xl border bg-surface object-contain p-1" /> : <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-surface-muted text-[10px] text-text-muted">No logo</div>}
            <div className="min-w-0 flex-1"><p className="truncate font-semibold text-text">{identityName}</p><p className="text-xs text-text-muted">School name is managed in your profile and stays authoritative.</p></div>
            <Link to="/profile" className="inline-flex shrink-0 items-center gap-1 text-sm font-bold text-primary">Manage logo <ExternalLink className="h-3.5 w-3.5" /></Link>
          </div>
        </div>

        <div>
          <section className="p-5 sm:p-7">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="text-lg font-semibold text-text">Choose your signature colour</h2><p className="mt-1 text-sm text-text-muted">Curated school palettes inspired by crest, uniform, and house-colour combinations. No unsafe custom colour codes.</p></div><p className="text-xs font-semibold text-text-faint">{PALETTES.length} themes</p></div>
            <div className="mt-5 grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-4">
              {PALETTES.map((palette) => {
                const active = palette.key === paletteKey;
                return <button key={palette.key} type="button" onClick={() => setPendingPaletteKey(palette.key)} aria-pressed={active} className={`group flex min-h-[7.25rem] flex-col items-start gap-2 rounded-xl border px-3 py-3 text-left transition-all sm:min-h-20 sm:flex-row sm:items-center sm:gap-3 sm:px-3.5 ${active ? "border-primary bg-primary-subtle shadow-sm ring-2 ring-primary/10" : "border-border/70 bg-surface hover:-translate-y-0.5 hover:border-border-strong hover:shadow-sm"}`}><span className="relative h-8 w-full shrink-0 overflow-hidden rounded-lg shadow-sm sm:h-11 sm:w-11 sm:rounded-xl"><span className="absolute inset-0" style={{ background: palette.primary }} /><span className="absolute bottom-0 right-0 h-5 w-1/2 rounded-tl-lg sm:h-6 sm:w-6 sm:rounded-tl-xl" style={{ background: palette.accent }} /></span><span className="min-w-0 flex-1"><span className="flex items-start justify-between gap-1.5 text-sm font-semibold leading-5 text-text sm:items-center"><span className="min-w-0 break-words">{palette.name}</span>{active ? <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground"><Check className="h-3 w-3" /></span> : null}</span><span className="mt-0.5 block text-xs leading-4 text-text-muted sm:truncate">{palette.description}</span></span></button>;
              })}
            </div>
          </section>
        </div>

        <div className="border-t border-border/60 bg-surface px-5 py-3 text-xs text-text-muted sm:px-7">
          {enabled ? `${selected.name} is live across your school.` : `${selected.name} is selected. Choose a palette to publish it for everyone.`}
        </div>
      </Card>

      <ConfirmDialog open={resetOpen} title="Restore Weave colours?" description="This turns school colours off and restores the default palette for every user. Your school name, logo and workspace appearance mode stay unchanged." cancelLabel="Cancel" confirmLabel="Restore colours" variant="danger" isLoading={busy === "reset"} onCancel={() => setResetOpen(false)} onConfirm={restoreDefaults} />
      <Modal
        open={Boolean(pendingPalette)}
        title={pendingPalette ? `Use ${pendingPalette.name}?` : "Use colour theme?"}
        description={pendingPalette?.description}
        onClose={closePaletteDialog}
        placement="center"
        footer={pendingPalette ? (
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" onClick={closePaletteDialog} disabled={Boolean(busy)}>Cancel</Button>
            <Button type="button" onClick={() => persist(enabled ? "save" : "enable", pendingPalette.key)} disabled={Boolean(busy) || (enabled && pendingPalette.key === baseline)}>
              <Save className="h-4 w-4" />{enabled ? "Save changes" : "Save and publish"}
            </Button>
          </div>
        ) : null}
      >
        {pendingPalette ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-text-faint">Preview</p>
              <div className="inline-flex rounded-xl border border-border bg-surface p-1">
                <button type="button" onClick={() => setPreviewMode("light")} aria-pressed={previewMode === "light"} className={`flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold transition ${previewMode === "light" ? "bg-primary text-primary-foreground" : "text-text-muted hover:bg-surface-muted"}`}><Sun className="h-3.5 w-3.5" /> Light</button>
                <button type="button" onClick={() => setPreviewMode("dark")} aria-pressed={previewMode === "dark"} className={`flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold transition ${previewMode === "dark" ? "bg-primary text-primary-foreground" : "text-text-muted hover:bg-surface-muted"}`}><Moon className="h-3.5 w-3.5" /> Dark</button>
              </div>
            </div>
            <ThemePreview palette={pendingPalette} dark={previewMode === "dark"} />
            <p className="text-sm leading-6 text-text-muted">
              This applies {pendingPalette.name} to navigation, primary actions, dashboard highlights, and key workspace accents for this school.
            </p>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
