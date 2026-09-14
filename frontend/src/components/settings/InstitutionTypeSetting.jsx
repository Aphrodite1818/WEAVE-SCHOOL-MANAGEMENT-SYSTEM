import { AlertTriangle, Building2, CheckCircle2, RefreshCcw, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import TypedConfirmationDialog from "../../features/academic-admin/TypedConfirmationDialog";
import { useToast } from "../../hooks/useToast";
import { authSession, getErrorMessage } from "../../services/api";
import { tenantService } from "../../services/tenant.service";
import Button from "../ui/Button";
import Card from "../ui/Card";
import Modal from "../ui/Modal";

const OPTIONS = [
  { value: "PRIMARY_SCHOOL", label: "Primary school" },
  { value: "SECONDARY_SCHOOL", label: "Secondary school" },
];

const RESET_CONFIRMATION = "RESET_ACADEMIC_STRUCTURE";

const labelForType = (value) =>
  OPTIONS.find((option) => option.value === value)?.label || "Not set";

export default function InstitutionTypeSetting({ role }) {
  const user = authSession.getUser() || {};
  const tenantId = user.tenant_id || user.tenant?.id || null;
  const { showError, showSuccess } = useToast();
  const [tenant, setTenant] = useState(null);
  const [target, setTarget] = useState("");
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [previewing, setPreviewing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [confirmDirect, setConfirmDirect] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);

  const isAdmin = String(role || "").toLowerCase() === "admin";

  useEffect(() => {
    if (!isAdmin || !tenantId) {
      setLoading(false);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    tenantService
      .getTenant(tenantId)
      .then((row) => {
        if (cancelled) return;
        setTenant(row);
        setTarget(row?.institution_type || "");
      })
      .catch((error) => {
        if (!cancelled) showError(getErrorMessage(error, "Could not load school structure settings."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isAdmin, showError, tenantId]);

  useEffect(() => {
    if (!tenantId || !target || target === tenant?.institution_type) {
      setPreview(null);
      return undefined;
    }

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setPreviewing(true);
      try {
        const result = await tenantService.previewInstitutionTypeTransition(tenantId, target);
        if (!cancelled) setPreview(result);
      } catch (error) {
        if (!cancelled) {
          setPreview(null);
          showError(getErrorMessage(error, "Could not check this institution type change."));
        }
      } finally {
        if (!cancelled) setPreviewing(false);
      }
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [showError, target, tenant?.institution_type, tenantId]);

  const resetSummary = useMemo(() => {
    const levels = Number(preview?.reset_counts?.academic_levels || 0);
    const departments = Number(preview?.reset_counts?.departments || 0);
    return [
      levels ? `${levels} draft academic level${levels === 1 ? "" : "s"}` : null,
      departments ? `${departments} unused department${departments === 1 ? "" : "s"}` : null,
    ].filter(Boolean);
  }, [preview]);

  if (!isAdmin || !tenantId) return null;

  const currentType = tenant?.institution_type;
  const unchanged = !target || target === currentType;
  const mode = preview?.mode;

  const apply = async (confirmation = null) => {
    if (!target || unchanged) return;
    setApplying(true);
    try {
      await tenantService.applyInstitutionTypeTransition(tenantId, {
        institution_type: target,
        confirmation,
      });
      showSuccess("Institution type updated. Reloading the workspace structure...");
      window.setTimeout(() => window.location.reload(), 350);
    } catch (error) {
      showError(getErrorMessage(error, "Could not change the institution type."));
    } finally {
      setApplying(false);
      setConfirmDirect(false);
      setConfirmReset(false);
    }
  };

  return (
    <>
      <Card className="overflow-hidden">
        <div className="border-b border-border bg-surface-muted/45 p-5 sm:p-6">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
              <Building2 className="h-5 w-5" />
            </span>
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-primary">School structure</p>
              <h2 className="mt-1 text-lg font-semibold text-text">Institution type</h2>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-text-muted">
                This controls which academic categories Weave makes available. Protected academic evidence is never deleted to make a type change possible.
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-5 p-5 sm:p-6">
          {loading ? (
            <p className="text-sm text-text-muted">Loading school structure...</p>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(18rem,0.8fr)]">
                <label className="block">
                  <span className="mb-2 block text-sm font-semibold text-text">Institution type</span>
                  <select
                    value={target}
                    onChange={(event) => setTarget(event.target.value)}
                    disabled={applying}
                    className="min-h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm font-medium text-text outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10"
                  >
                    {OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>

                <div className="rounded-xl border border-border bg-surface-muted/35 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">Current structure</p>
                  <p className="mt-2 text-sm font-semibold text-text">{labelForType(currentType)}</p>
                  <p className="mt-1 text-xs leading-5 text-text-muted">
                    Weave checks the academic hierarchy before any established type is changed.
                  </p>
                </div>
              </div>

              {previewing ? (
                <div className="flex items-center gap-2 rounded-xl border border-border bg-surface-muted/35 px-4 py-3 text-sm text-text-muted">
                  <RefreshCcw className="h-4 w-4 animate-spin" />
                  Checking academic dependencies...
                </div>
              ) : null}

              {!previewing && mode === "DIRECT" && !unchanged ? (
                <div className="rounded-xl border border-success/35 bg-success/10 p-4">
                  <div className="flex items-start gap-3">
                    <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-success" />
                    <div>
                      <p className="text-sm font-semibold text-text">Safe direct change</p>
                      <p className="mt-1 text-sm leading-6 text-text-muted">
                        No institution-specific academic structure needs to be removed. The new category catalogue can be applied directly.
                      </p>
                    </div>
                  </div>
                </div>
              ) : null}

              {!previewing && mode === "RESET_REQUIRED" ? (
                <div className="rounded-xl border border-warning/40 bg-warning-soft p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
                    <div>
                      <p className="text-sm font-semibold text-text">Disposable setup must be reset</p>
                      <p className="mt-1 text-sm leading-6 text-text-muted">
                        Only draft, unused setup will be removed. No class, curriculum, enrollment, published level, or historical academic evidence is eligible for this reset.
                      </p>
                      {resetSummary.length ? (
                        <p className="mt-2 text-sm font-medium text-text">Reset: {resetSummary.join(" · ")}</p>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : null}

              {!previewing && mode === "BLOCKED" ? (
                <div className="rounded-xl border border-error/35 bg-error/10 p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-error" />
                    <div>
                      <p className="text-sm font-semibold text-text">Institution type is locked by academic evidence</p>
                      <p className="mt-1 text-sm leading-6 text-text-muted">
                        Weave will not delete or reinterpret established academic records to make this change.
                      </p>
                      {preview.blocker_messages?.length ? (
                        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-text-muted">
                          {preview.blocker_messages.map((message) => (
                            <li key={message}>{message}</li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : null}

              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
                <div className="flex items-center gap-2 text-xs text-text-muted">
                  <CheckCircle2 className="h-4 w-4 text-success" />
                  Existing results, attendance, enrollments, CBT evidence, and published records are preserved.
                </div>
                <Button
                  type="button"
                  disabled={unchanged || previewing || applying || mode === "BLOCKED" || !mode}
                  onClick={() => {
                    if (mode === "RESET_REQUIRED") setConfirmReset(true);
                    else setConfirmDirect(true);
                  }}
                >
                  Review change
                </Button>
              </div>
            </>
          )}
        </div>
      </Card>

      <Modal
        open={confirmDirect}
        title="Change institution type"
        description={`Change this school from ${labelForType(currentType)} to ${labelForType(target)}? The academic category catalogue will update immediately.`}
        onClose={applying ? undefined : () => setConfirmDirect(false)}
        closeOnOverlay={!applying}
        footer={
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" disabled={applying} onClick={() => setConfirmDirect(false)}>
              Cancel
            </Button>
            <Button type="button" disabled={applying} onClick={() => apply(null)}>
              {applying ? "Changing..." : "Change institution type"}
            </Button>
          </div>
        }
      >
        <p className="text-sm leading-6 text-text-muted">
          Weave found no protected or disposable institution-specific academic structure that needs removal.
        </p>
      </Modal>

      <TypedConfirmationDialog
        open={confirmReset}
        title="Reset draft academic structure"
        description={`Changing to ${labelForType(target)} requires removing only the disposable draft setup listed below.`}
        confirmationText={preview?.confirmation_text || RESET_CONFIRMATION}
        confirmLabel="Reset setup and change type"
        isLoading={applying}
        onCancel={() => setConfirmReset(false)}
        onConfirm={(confirmation) => apply(confirmation)}
      >
        <div className="rounded-lg border border-error/25 bg-error/10 p-3 text-sm leading-6 text-text-muted">
          {resetSummary.length
            ? `This will remove ${resetSummary.join(" and ")}.`
            : "This will remove disposable draft academic setup."} Protected academic evidence cannot reach this confirmation state.
        </div>
      </TypedConfirmationDialog>
    </>
  );
}
