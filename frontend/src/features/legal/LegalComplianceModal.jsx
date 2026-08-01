import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { legalComplianceService } from "../../services/legalComplianceService";
import Button from "../../components/ui/Button";
import Modal from "../../components/ui/Modal";
import LegalComplianceContent from "./LegalComplianceContent";

function LegalComplianceModal({ open, onAccepted, onRejected, role = "admin" }) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (open) {
      setConfirmed(false);
      setError("");
    }
  }, [open]);

  const acceptTerms = async () => {
    setSubmitting(true);
    setError("");
    try {
      const status = await legalComplianceService.accept();
      onAccepted?.(status);
    } catch (err) {
      setError(err?.message || "We could not record your acceptance. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      title="Review Weave Legal Terms"
      description="Accept these terms before onboarding and guided setup continue."
      closeOnOverlay={false}
      showClose={false}
      className="max-w-3xl"
      footer={(
        <div className="space-y-3">
          {error ? (
            <div className="rounded-xl border border-error/25 bg-error-soft px-3 py-2 text-sm font-medium text-error">
              {error}
            </div>
          ) : null}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
            <Button type="button" variant="outline" disabled={submitting} onClick={onRejected}>
              <XCircle className="h-4 w-4" />
              Reject for now
            </Button>
            <Button type="button" disabled={submitting || !confirmed} onClick={acceptTerms}>
              {submitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 className="h-4 w-4" />
              )}
              Agree and continue
            </Button>
          </div>
        </div>
      )}
    >
      <div className="space-y-5">
        <LegalComplianceContent compact role={role} />
        <label className="flex items-start gap-3 rounded-2xl border border-border bg-surface-muted/40 p-4">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
            className="mt-1 h-4 w-4 rounded border-border accent-primary"
          />
          <span className="text-sm leading-6 text-text-muted">
            I have read and agree to the Weave legal and compliance terms for my role.
          </span>
        </label>
      </div>
    </Modal>
  );
}

export default LegalComplianceModal;
